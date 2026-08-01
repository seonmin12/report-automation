"""
4단계 마지막 최적화: 청크 처리.

0단계에서 분류한 대로, `check_missing_mapping`(매핑누락)과
`check_inactive_product_usage`(비활성사용)만 청크 처리 대상이다. 둘 다 "매핑표
쪽에서 만든 작은 코드 집합에 RAW 각 행이 속하는지"만 보는 행 단위 독립 검증이라,
RAW를 파일에서 chunksize 단위로 스트리밍하면서 청크별로 부분 결과를 누적해도
전체를 한 번에 본 것과 똑같은 결과가 나온다. 나머지 2종(중복/명칭불일치)과
실적비교는 그대로 전체 데이터가 필요해서 청크로 안 쪼갠다 (건드리지 않음).

이 최적화를 dtype/usecols/merge 3개와 같은 표에 안 넣고 따로 뺀 이유
--------------------------------------------------------------------
dtype/usecols/merge는 "전체 파이프라인"의 파일로드~merge 단계에 적용돼서
전체 파이프라인 벤치마크(run_optimizations.py)에 자연스럽게 녹아든다. 반면
청크 처리는 이 프로젝트 파이프라인 안에서는 애매하다 — 같은 요청 안에서
`check_name_mismatch`와 `aggregate_by_operator_product`가 어차피 RAW 전체를
groupby해야 하므로, 매핑누락/비활성사용만 청크로 스트리밍해도 전체 파이프라인의
피크 메모리는 줄어들지 않는다 (다른 단계가 이미 전체를 메모리에 올려놓기
때문). 그래서 이 파일은 "이 두 검증만 독립적으로 수행해야 하는 상황"(예: 이
두 검증만 먼저 빠르게 훑어야 하거나, RAW 파일이 메모리에 다 못 올라갈 만큼
훨씬 큰 경우)을 가정한 별도 실험이다. RESULTS.md에도 이 전제를 명시한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import COL_OPERATOR_CODE, COL_PRODUCT_CODE, COL_PRODUCT_NAME, COL_USE_YN, COL_TXN_ID, USE_YN_INACTIVE
from src.validate import COL_TXN_COUNT

_RESULT_COLUMNS = [COL_PRODUCT_CODE, COL_PRODUCT_NAME, COL_OPERATOR_CODE, COL_TXN_COUNT]


def _accumulate_chunked(csv_path: Path, target_codes: set[str], chunksize: int) -> pd.DataFrame:
    """target_codes에 속하는 상품코드의 (첫 상품명, 첫 사업자코드, 거래건수)를
    청크 단위로 누적. `groupby(...).agg({'first', 'first', 'count'})`와 동일한
    결과가 나오도록, 원본 파일 순서대로(=청크 순서대로) '첫 값'을 기록한다.
    """
    first_name: dict[str, str] = {}
    first_operator: dict[str, str] = {}
    counts: dict[str, int] = {}

    usecols = [COL_TXN_ID, COL_OPERATOR_CODE, COL_PRODUCT_CODE, COL_PRODUCT_NAME]
    for chunk in pd.read_csv(csv_path, encoding="utf-8-sig", usecols=usecols, chunksize=chunksize):
        matched = chunk[chunk[COL_PRODUCT_CODE].isin(target_codes)]
        if matched.empty:
            continue
        for code, group in matched.groupby(COL_PRODUCT_CODE, sort=False):
            counts[code] = counts.get(code, 0) + len(group)
            if code not in first_name:
                first_name[code] = group[COL_PRODUCT_NAME].iloc[0]
                first_operator[code] = group[COL_OPERATOR_CODE].iloc[0]

    if not counts:
        return pd.DataFrame(columns=_RESULT_COLUMNS)

    rows = [
        {
            COL_PRODUCT_CODE: code,
            COL_PRODUCT_NAME: first_name[code],
            COL_OPERATOR_CODE: first_operator[code],
            COL_TXN_COUNT: count,
        }
        for code, count in counts.items()
    ]
    # pandas groupby 기본(sort=True)과 동일하게 상품코드 기준 정렬해서 반환
    return pd.DataFrame(rows, columns=_RESULT_COLUMNS).sort_values(COL_PRODUCT_CODE).reset_index(drop=True)


def check_missing_mapping_chunked(csv_path: Path, mapping_df: pd.DataFrame, chunksize: int) -> pd.DataFrame:
    """validate.check_missing_mapping()과 동일한 결과를, RAW 파일을 청크로
    스트리밍하며 계산한다 (raw_df 전체를 메모리에 올리지 않음)."""
    mapped_codes = set(mapping_df[COL_PRODUCT_CODE])
    # "매핑에 없는 코드"는 화이트리스트가 아니라 블랙리스트라서, 청크마다
    # "mapped_codes에 없는 것"을 걸러야 한다 — target_codes를 미리 못 정하므로
    # isin(mapped_codes)의 부정을 청크 안에서 직접 판정한다.
    first_name: dict[str, str] = {}
    first_operator: dict[str, str] = {}
    counts: dict[str, int] = {}

    usecols = [COL_TXN_ID, COL_OPERATOR_CODE, COL_PRODUCT_CODE, COL_PRODUCT_NAME]
    for chunk in pd.read_csv(csv_path, encoding="utf-8-sig", usecols=usecols, chunksize=chunksize):
        missing = chunk[~chunk[COL_PRODUCT_CODE].isin(mapped_codes)]
        if missing.empty:
            continue
        for code, group in missing.groupby(COL_PRODUCT_CODE, sort=False):
            counts[code] = counts.get(code, 0) + len(group)
            if code not in first_name:
                first_name[code] = group[COL_PRODUCT_NAME].iloc[0]
                first_operator[code] = group[COL_OPERATOR_CODE].iloc[0]

    if not counts:
        return pd.DataFrame(columns=_RESULT_COLUMNS)
    rows = [
        {
            COL_PRODUCT_CODE: code,
            COL_PRODUCT_NAME: first_name[code],
            COL_OPERATOR_CODE: first_operator[code],
            COL_TXN_COUNT: count,
        }
        for code, count in counts.items()
    ]
    return pd.DataFrame(rows, columns=_RESULT_COLUMNS).sort_values(COL_PRODUCT_CODE).reset_index(drop=True)


def check_inactive_product_usage_chunked(
    csv_path: Path, mapping_df: pd.DataFrame, chunksize: int
) -> pd.DataFrame:
    """validate.check_inactive_product_usage()와 동일한 결과를 청크 스트리밍으로."""
    inactive_codes = set(
        mapping_df.loc[mapping_df[COL_USE_YN] == USE_YN_INACTIVE, COL_PRODUCT_CODE]
    )
    return _accumulate_chunked(csv_path, inactive_codes, chunksize)
