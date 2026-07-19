"""
더미데이터 생성 모듈.

3종의 더미파일을 만든다.
1. 포털 실적 Excel (data/portal/portal_performance.xlsx)
2. RAW 거래 CSV (data/raw/raw_transactions.csv)
3. 요금제/상품 매핑 기준표 Excel (data/mapping/product_mapping.xlsx)

검증 로직이 실제로 뭔가 잡아낼 수 있도록, 의도적으로 다음 '결함 케이스'를 섞어 넣는다.
- 매핑 기준표에 등록되지 않은 상품코드로 발생한 RAW 거래 (매핑 누락)
- 매핑 기준표에 같은 상품코드가 중복 등록된 케이스 (중복)
- 사용여부가 '비활성'인 상품코드로 발생한 RAW 거래 (비활성 상품 사용)
- 포털/RAW/매핑표에서 같은 상품코드인데 상품명이 서로 다른 케이스 (명칭 불일치)
- 포털 집계값과 RAW 집계값이 의도적으로 어긋나는 케이스 (실적 비교 대상)
"""

import random
from datetime import datetime, timedelta

import pandas as pd

from config import (
    N_PRODUCTS,
    N_RAW_TRANSACTIONS,
    PORTAL_FILE,
    RAW_FILE,
    MAPPING_FILE,
    DEFAULT_AS_OF_DATE,
    DUMMY_OPERATORS,
    PLAN_TYPES,
    PAYMENT_TYPES,
    CHANNELS,
    RANDOM_SEED,
    COL_OPERATOR_CODE,
    COL_OPERATOR_NAME,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_PLAN_TYPE,
    COL_PAYMENT_TYPE,
    COL_CHANNEL,
    COL_USE_YN,
    COL_MAPPING_DATE,
    COL_NOTE,
    COL_TXN_ID,
    COL_TXN_DATE,
    COL_TXN_TYPE,
    COL_REGISTERED_AT,
    COL_NEW_COUNT,
    COL_CHURN_COUNT,
    COL_NET_COUNT,
    USE_YN_ACTIVE,
    USE_YN_INACTIVE,
    TXN_TYPE_NEW,
    TXN_TYPE_CHURN,
)

_rng = random.Random(RANDOM_SEED)

# ------------------------------------------------------------------
# 결함 케이스 규모 설정
# ------------------------------------------------------------------
N_INACTIVE_PRODUCTS = 4          # 매핑표에서 '비활성' 처리할 상품 수
N_DUPLICATE_PRODUCTS = 2         # 매핑표에서 중복 등록할 상품 수
N_UNMAPPED_PRODUCT_CODES = 3     # 매핑표에 없는데 RAW에는 등장하는 상품코드 수
N_NAME_MISMATCH_PRODUCTS = 3     # RAW 상품명을 매핑표 표준명과 다르게 기록할 상품 수

UNMAPPED_TXN_RATIO = 0.03        # RAW 거래 중 매핑 누락 상품코드 비율
INACTIVE_TXN_RATIO = 0.02        # RAW 거래 중 비활성 상품코드 비율
PREV_MONTH_TXN_RATIO = 0.15      # RAW 거래 중 전월 거래 비율 (당월 필터링 테스트용)
NEW_TXN_RATIO = 0.7              # 거래유형이 '신규'일 비율 (나머지는 '해지')

PORTAL_PERTURB_RATIO = 0.12      # 포털 집계값을 의도적으로 어긋나게 할 행 비율
PORTAL_ONLY_ROWS = 2              # 포털에만 존재하는 상품 행 개수
RAW_ONLY_DROP_ROWS = 2             # 포털에서 누락시켜 RAW에만 존재하게 할 상품 행 개수


def generate_product_mapping(n_products: int = N_PRODUCTS) -> pd.DataFrame:
    """요금제/상품 매핑 기준표 더미데이터 생성.

    - 상품코드/표준상품명/요금제유형/사업자코드/사용여부/매핑등록일/비고 컬럼 생성
    - 일부 상품코드를 의도적으로 중복 등록 (중복 검증용)
    - 일부 상품을 '비활성'으로 설정 (비활성 사용 검증용)
    """
    rows = []
    for i in range(1, n_products + 1):
        operator = DUMMY_OPERATORS[i % len(DUMMY_OPERATORS)]
        plan_type = PLAN_TYPES[i % len(PLAN_TYPES)]
        registered_at = DEFAULT_AS_OF_DATE - timedelta(days=_rng.randint(30, 365))

        rows.append(
            {
                COL_PRODUCT_CODE: f"PRD{i:03d}",
                COL_PRODUCT_NAME: f"{plan_type} {i:03d}",
                COL_PLAN_TYPE: plan_type,
                COL_OPERATOR_CODE: operator[COL_OPERATOR_CODE],
                COL_USE_YN: USE_YN_ACTIVE,
                COL_MAPPING_DATE: registered_at,
                COL_NOTE: "",
            }
        )

    mapping_df = pd.DataFrame(rows)

    # 일부 상품을 비활성 처리 (비활성 상품 사용 검증용)
    inactive_idx = _rng.sample(list(mapping_df.index), N_INACTIVE_PRODUCTS)
    mapping_df.loc[inactive_idx, COL_USE_YN] = USE_YN_INACTIVE
    mapping_df.loc[inactive_idx, COL_NOTE] = "서비스 종료 상품"

    # 일부 상품코드를 중복 등록 (중복 검증용)
    remaining_idx = [idx for idx in mapping_df.index if idx not in inactive_idx]
    dup_source_idx = _rng.sample(remaining_idx, N_DUPLICATE_PRODUCTS)
    dup_rows = mapping_df.loc[dup_source_idx].copy()
    dup_rows[COL_NOTE] = "중복 등록"
    mapping_df = pd.concat([mapping_df, dup_rows], ignore_index=True)

    return mapping_df.sort_values(COL_PRODUCT_CODE).reset_index(drop=True)


def generate_raw_transactions(
    mapping_df: pd.DataFrame, n_rows: int = N_RAW_TRANSACTIONS
) -> pd.DataFrame:
    """RAW 거래 데이터 더미 생성.

    - 거래ID/처리일자/사업자코드/상품코드/상품명/거래유형/선후불구분/채널/등록시각 생성
    - mapping_df에 없는 상품코드를 일부 섞어서 생성 (매핑 누락 검증용)
    - mapping_df 상 비활성 상품코드도 일부 사용해서 생성 (비활성 사용 검증용)
    - 특정 상품코드는 상품명을 매핑표 표준명과 다르게 고정 기록 (명칭 불일치 검증용)
    """
    unique_mapping = mapping_df.drop_duplicates(COL_PRODUCT_CODE).set_index(COL_PRODUCT_CODE)
    active_codes = unique_mapping.index[unique_mapping[COL_USE_YN] == USE_YN_ACTIVE].tolist()
    inactive_codes = unique_mapping.index[unique_mapping[COL_USE_YN] == USE_YN_INACTIVE].tolist()
    unmapped_codes = [f"PRDX{i:02d}" for i in range(1, N_UNMAPPED_PRODUCT_CODES + 1)]

    code_to_name = unique_mapping[COL_PRODUCT_NAME]
    code_to_operator = unique_mapping[COL_OPERATOR_CODE]

    # 특정 상품코드는 RAW에서 항상 매핑표 표준명과 다른 이름으로 기록 (명칭 불일치 케이스)
    mismatch_codes = set(_rng.sample(active_codes, N_NAME_MISMATCH_PRODUCTS))

    month_start = DEFAULT_AS_OF_DATE.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    current_month_span = (DEFAULT_AS_OF_DATE - month_start).days
    prev_month_span = (prev_month_end - prev_month_start).days

    rows = []
    for i in range(1, n_rows + 1):
        draw = _rng.random()
        if draw < UNMAPPED_TXN_RATIO:
            product_code = _rng.choice(unmapped_codes)
            operator_code = _rng.choice(DUMMY_OPERATORS)[COL_OPERATOR_CODE]
            product_name = f"미확인상품_{product_code}"
        elif draw < UNMAPPED_TXN_RATIO + INACTIVE_TXN_RATIO and inactive_codes:
            product_code = _rng.choice(inactive_codes)
            operator_code = code_to_operator[product_code]
            product_name = code_to_name[product_code]
        else:
            product_code = _rng.choice(active_codes)
            operator_code = code_to_operator[product_code]
            product_name = code_to_name[product_code]

        if product_code in mismatch_codes:
            product_name = f"{product_name}(수정전)"

        if _rng.random() < PREV_MONTH_TXN_RATIO:
            txn_date = prev_month_start + timedelta(days=_rng.randint(0, prev_month_span))
        else:
            txn_date = month_start + timedelta(days=_rng.randint(0, current_month_span))

        txn_type = TXN_TYPE_NEW if _rng.random() < NEW_TXN_RATIO else TXN_TYPE_CHURN
        registered_at = datetime.combine(txn_date, datetime.min.time()) + timedelta(
            seconds=_rng.randint(0, 24 * 60 * 60 - 1)
        )

        rows.append(
            {
                COL_TXN_ID: f"TXN{i:06d}",
                COL_TXN_DATE: txn_date,
                COL_OPERATOR_CODE: operator_code,
                COL_PRODUCT_CODE: product_code,
                COL_PRODUCT_NAME: product_name,
                COL_TXN_TYPE: txn_type,
                COL_PAYMENT_TYPE: _rng.choice(PAYMENT_TYPES),
                COL_CHANNEL: _rng.choice(CHANNELS),
                COL_REGISTERED_AT: registered_at,
            }
        )

    return pd.DataFrame(rows)


def generate_portal_performance(raw_df: pd.DataFrame) -> pd.DataFrame:
    """포털 실적(집계) 더미 생성.

    raw_df를 사업자/상품 단위로 집계해서 만들되, 일부 값을 의도적으로
    어긋나게 조정하고 (포털-RAW 비교 검증용) 한쪽에만 존재하는 상품도 섞는다.
    """
    month_start = DEFAULT_AS_OF_DATE.replace(day=1)
    current_month_df = raw_df[
        (raw_df[COL_TXN_DATE] >= month_start) & (raw_df[COL_TXN_DATE] <= DEFAULT_AS_OF_DATE)
    ]

    operator_name_map = {op[COL_OPERATOR_CODE]: op[COL_OPERATOR_NAME] for op in DUMMY_OPERATORS}

    pivot = (
        current_month_df.groupby([COL_OPERATOR_CODE, COL_PRODUCT_CODE, COL_TXN_TYPE])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for txn_type in (TXN_TYPE_NEW, TXN_TYPE_CHURN):
        if txn_type not in pivot.columns:
            pivot[txn_type] = 0

    # 같은 사업자/상품 조합에서 RAW에 가장 마지막으로 기록된 상품명을 대표값으로 사용
    product_name = (
        current_month_df.sort_values(COL_REGISTERED_AT)
        .drop_duplicates([COL_OPERATOR_CODE, COL_PRODUCT_CODE], keep="last")[
            [COL_OPERATOR_CODE, COL_PRODUCT_CODE, COL_PRODUCT_NAME]
        ]
    )

    portal_df = pivot.merge(product_name, on=[COL_OPERATOR_CODE, COL_PRODUCT_CODE], how="left")
    portal_df = portal_df.rename(
        columns={TXN_TYPE_NEW: COL_NEW_COUNT, TXN_TYPE_CHURN: COL_CHURN_COUNT}
    )
    portal_df[COL_NET_COUNT] = portal_df[COL_NEW_COUNT] - portal_df[COL_CHURN_COUNT]
    portal_df[COL_OPERATOR_NAME] = portal_df[COL_OPERATOR_CODE].map(operator_name_map)
    portal_df = portal_df[
        [
            COL_OPERATOR_CODE,
            COL_OPERATOR_NAME,
            COL_PRODUCT_CODE,
            COL_PRODUCT_NAME,
            COL_NEW_COUNT,
            COL_CHURN_COUNT,
            COL_NET_COUNT,
        ]
    ]

    # 포털 집계값을 의도적으로 어긋나게 조정 (실적 비교 검증용)
    perturb_idx = _rng.sample(
        list(portal_df.index), max(1, int(len(portal_df) * PORTAL_PERTURB_RATIO))
    )
    for idx in perturb_idx:
        delta = _rng.randint(2, 8) * _rng.choice([-1, 1])
        portal_df.loc[idx, COL_NEW_COUNT] = max(0, portal_df.loc[idx, COL_NEW_COUNT] + delta)
        portal_df.loc[idx, COL_NET_COUNT] = (
            portal_df.loc[idx, COL_NEW_COUNT] - portal_df.loc[idx, COL_CHURN_COUNT]
        )

    # RAW에는 있지만 포털에서는 누락된 상품 (RAW에만 존재하는 케이스)
    drop_idx = _rng.sample(list(portal_df.index), min(RAW_ONLY_DROP_ROWS, len(portal_df)))
    portal_df = portal_df.drop(index=drop_idx).reset_index(drop=True)

    # 포털에만 존재하는 상품 (RAW에는 없는 실적) 추가
    extra_rows = []
    for i in range(PORTAL_ONLY_ROWS):
        operator = _rng.choice(DUMMY_OPERATORS)
        fake_code = f"PRDP{i + 1:02d}"
        new_count = _rng.randint(3, 10)
        churn_count = _rng.randint(0, 3)
        extra_rows.append(
            {
                COL_OPERATOR_CODE: operator[COL_OPERATOR_CODE],
                COL_OPERATOR_NAME: operator[COL_OPERATOR_NAME],
                COL_PRODUCT_CODE: fake_code,
                COL_PRODUCT_NAME: f"포털전용상품_{fake_code}",
                COL_NEW_COUNT: new_count,
                COL_CHURN_COUNT: churn_count,
                COL_NET_COUNT: new_count - churn_count,
            }
        )

    portal_df = pd.concat([portal_df, pd.DataFrame(extra_rows)], ignore_index=True)
    return portal_df


def main():
    mapping_df = generate_product_mapping()
    raw_df = generate_raw_transactions(mapping_df)
    portal_df = generate_portal_performance(raw_df)

    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    mapping_df.to_excel(MAPPING_FILE, index=False)
    raw_df.to_csv(RAW_FILE, index=False, encoding="utf-8-sig")
    portal_df.to_excel(PORTAL_FILE, index=False)

    print("더미데이터 생성 완료")
    print(f"  - 매핑표: {MAPPING_FILE} ({len(mapping_df)}행)")
    print(f"  - RAW 거래: {RAW_FILE} ({len(raw_df)}행)")
    print(f"  - 포털 실적: {PORTAL_FILE} ({len(portal_df)}행)")


if __name__ == "__main__":
    main()
