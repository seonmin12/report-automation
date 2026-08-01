"""
4단계 최적화 실험 — src/, main.py, web/app.py는 전혀 건드리지 않고, benchmark/
안에서만 "이렇게 바꾸면 얼마나 빨라지는가"를 검증한다. (사용자 확인: benchmark/
안에서만 실험하기로 결정)

기존 검증 로직(src/aggregate.py, src/compare.py, src/validate.py)은 그대로
import해서 쓴다. 여기서 바꾸는 건 오직 "파일을 어떻게 읽어들이는가"와 "merge
직전에 키 컬럼 dtype을 어떻게 맞추는가"뿐이다. 검증 로직 자체는 원본 함수를
그대로 호출하므로, 결과가 달라진다면 그건 버그다 (그래서 매 단계마다
check_accuracy.py로 원본과 동일한지 재확인한다).

최적화 레벨 (레벨이 올라갈수록 이전 레벨 위에 누적 적용):
  0: 베이스라인 (2단계와 동일 — dtype/usecols 미지정)
  1: dtype 명시 (저카디널리티 컬럼은 category)
  2: 1 + usecols (검증 파이프라인이 실제로 안 쓰는 컬럼 제외)
  3: 2 + merge 키 dtype 정합 (portal/raw 양쪽에서 독립적으로 만들어진 category를
     merge 직전에 통일된 CategoricalDtype으로 맞춤)

청크 처리(원래 계획의 4번)는 여기 포함하지 않고 `chunked_check.py`에 별도로
분리했다 — 이유는 그 파일 docstring에 설명.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    COL_CHANNEL,
    COL_MAPPING_DATE,
    COL_NET_COUNT,
    COL_NEW_COUNT,
    COL_NOTE,
    COL_CHURN_COUNT,
    COL_OPERATOR_CODE,
    COL_OPERATOR_NAME,
    COL_PAYMENT_TYPE,
    COL_PLAN_TYPE,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_REGISTERED_AT,
    COL_TXN_DATE,
    COL_TXN_ID,
    COL_TXN_TYPE,
    COL_USE_YN,
)
from src import compare as compare_module

# ------------------------------------------------------------------
# 레벨 1: dtype
# ------------------------------------------------------------------
# 저카디언리티 컬럼(값 종류가 몇 개 안 되는데 수십만 행에 반복되는 컬럼)은
# category로 지정하면 메모리를 크게 아낀다. 상품코드는 카디널리티가 상대적으로
# 높아도(수백 개) 행 수 대비로는 여전히 압도적으로 반복되는 컬럼이라 포함했다.
# 거래ID는 매 행 고유값이라 category로 하면 오히려 손해라 제외.
#
# 상품명(COL_PRODUCT_NAME)은 처음엔 category로 넣었다가 뺐다 — 실제로 돌려보니
# validate.check_name_mismatch()가 `.groupby(...).agg(lambda s: sorted(set(s)))`
# 처럼 그룹별로 "이름 리스트"를 만드는데, 원본 컬럼이 category면 pandas가 이
# 결과(list)를 다시 원래 category dtype으로 캐스팅하려다 `TypeError: unhashable
# type: 'list'`로 죽는다. 정확도 재확인 단계에서 걸러졌다 — dtype 최적화가
# 검증 로직의 "동작"까지 바꿔버릴 뻔한 사례라 기록해 둔다.
RAW_DTYPE = {
    COL_OPERATOR_CODE: "category",
    COL_PRODUCT_CODE: "category",
    COL_TXN_TYPE: "category",
    COL_PAYMENT_TYPE: "category",
    COL_CHANNEL: "category",
}
MAPPING_DTYPE = {
    COL_PRODUCT_CODE: "category",
    COL_PLAN_TYPE: "category",
    COL_OPERATOR_CODE: "category",
    COL_USE_YN: "category",
    COL_NOTE: "category",
}
PORTAL_DTYPE = {
    COL_OPERATOR_CODE: "category",
    COL_OPERATOR_NAME: "category",
    COL_PRODUCT_CODE: "category",
    COL_NEW_COUNT: "int32",
    COL_CHURN_COUNT: "int32",
    COL_NET_COUNT: "int32",
}

# ------------------------------------------------------------------
# 레벨 2: usecols
# ------------------------------------------------------------------
# aggregate.py / compare.py / validate.py 소스를 직접 확인해서, raw_df/mapping_df의
# 원본 컬럼 중 실제로 한 번도 안 읽히는 것만 뺐다. (0단계 조사에서는 못 봤던,
# 이번에 코드 재확인하며 찾은 것: 선후불구분/채널/등록시각은 RAW를 읽어들인 뒤
# 검증 파이프라인 어디서도 쓰이지 않고, 요금제유형/비고도 매핑표에서 마찬가지다.
# portal_performance.xlsx는 7개 컬럼이 전부 쓰여서 줄일 게 없다.)
RAW_USECOLS = [
    COL_TXN_ID,
    COL_TXN_DATE,
    COL_OPERATOR_CODE,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_TXN_TYPE,
]
MAPPING_USECOLS = [
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_OPERATOR_CODE,
    COL_USE_YN,
    COL_MAPPING_DATE,
]


def load_files(data_dir: Path, level: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """레벨에 따라 다른 방식으로 3개 파일을 읽는다.

    레벨 0은 main.py/web/app.py가 지금 실제로 하는 것과 동일한 무지정 읽기다.
    """
    if level == 0:
        portal_df = pd.read_excel(data_dir / "portal_performance.xlsx")
        raw_df = pd.read_csv(data_dir / "raw_transactions.csv", encoding="utf-8-sig")
        mapping_df = pd.read_excel(data_dir / "product_mapping.xlsx")
        return portal_df, raw_df, mapping_df

    if level == 1:
        portal_df = pd.read_excel(data_dir / "portal_performance.xlsx", dtype=PORTAL_DTYPE)
        raw_df = pd.read_csv(
            data_dir / "raw_transactions.csv", encoding="utf-8-sig", dtype=RAW_DTYPE
        )
        mapping_df = pd.read_excel(data_dir / "product_mapping.xlsx", dtype=MAPPING_DTYPE)
        return portal_df, raw_df, mapping_df

    # level 2, 3: dtype + usecols (레벨 3은 merge 직전 처리만 다르므로 로딩은 2와 동일)
    portal_df = pd.read_excel(data_dir / "portal_performance.xlsx", dtype=PORTAL_DTYPE)
    raw_df = pd.read_csv(
        data_dir / "raw_transactions.csv",
        encoding="utf-8-sig",
        dtype=RAW_DTYPE,
        usecols=RAW_USECOLS,
    )
    mapping_df = pd.read_excel(
        data_dir / "product_mapping.xlsx", dtype=MAPPING_DTYPE, usecols=MAPPING_USECOLS
    )
    return portal_df, raw_df, mapping_df


def compare_portal_vs_raw(
    portal_df: pd.DataFrame, raw_agg_df: pd.DataFrame, align_merge_dtype: bool
) -> pd.DataFrame:
    """merge 키 dtype을 맞추고 나서, 원본 compare.compare_portal_vs_raw를 그대로 호출한다.

    비교 로직 자체는 절대 안 바꾼다 — 여기서 하는 일은 merge 직전에
    양쪽 DataFrame의 사업자코드/상품코드 컬럼이 같은 CategoricalDtype을
    쓰도록 맞추는 것뿐이다. portal_df는 파일에서 직접 읽은 category이고,
    raw_agg_df(=aggregate_by_operator_product 결과)는 raw_df에서 파생된
    category라서, 둘의 category 집합(.categories)이 서로 다를 수 있다.
    dtype은 둘 다 'category'로 같아 보여도 categories가 다르면 pandas가
    내부적으로 더 느린 경로를 타거나 경고를 낸다.
    """
    if not align_merge_dtype:
        return compare_module.compare_portal_vs_raw(portal_df, raw_agg_df)

    portal_df = portal_df.copy()
    raw_agg_df = raw_agg_df.copy()

    for col in (COL_OPERATOR_CODE, COL_PRODUCT_CODE):
        left = portal_df[col]
        right = raw_agg_df[col]
        if isinstance(left.dtype, pd.CategoricalDtype) or isinstance(right.dtype, pd.CategoricalDtype):
            union_categories = pd.Index(
                sorted(set(left.astype(str).unique()) | set(right.astype(str).unique()))
            )
            unified = pd.CategoricalDtype(categories=union_categories)
            portal_df[col] = left.astype(str).astype(unified)
            raw_agg_df[col] = right.astype(str).astype(unified)

    return compare_module.compare_portal_vs_raw(portal_df, raw_agg_df)
