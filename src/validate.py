"""
매핑/데이터 정합성 검증 모듈 ('요금제 미매핑 현황' 대응).

RAW 데이터와 매핑 기준표를 대조하여 4가지 이슈를 검출한다.
1. 매핑 누락: RAW에는 있는데 매핑표에 없는 상품코드
2. 중복: 매핑표에 같은 상품코드가 두 번 이상 등록됨
3. 비활성 상품 사용: 매핑표 상 사용여부가 '비활성'인데 RAW에서 거래가 발생함
4. 상품명 불일치: 동일 상품코드에 대해 RAW/포털/매핑표의 상품명이 서로 다름
"""

import pandas as pd

from config import (
    COL_OPERATOR_CODE,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_TXN_ID,
    COL_USE_YN,
    USE_YN_INACTIVE,
)

# 검증 결과 전용 컬럼명 (config.py의 공통 컬럼과 달리 이 모듈 내부에서만 쓰임)
COL_TXN_COUNT = "거래건수"
COL_MAPPING_NAME = "매핑표상품명"
COL_RAW_NAME = "RAW상품명"
COL_PORTAL_NAME = "포털상품명"


def check_missing_mapping(raw_df: pd.DataFrame, mapping_df: pd.DataFrame) -> pd.DataFrame:
    """RAW에는 존재하지만 매핑표에 없는 상품코드를 찾는다."""
    mapped_codes = set(mapping_df[COL_PRODUCT_CODE])
    missing_df = raw_df[~raw_df[COL_PRODUCT_CODE].isin(mapped_codes)]

    columns = [COL_PRODUCT_CODE, COL_PRODUCT_NAME, COL_OPERATOR_CODE, COL_TXN_COUNT]
    if missing_df.empty:
        return pd.DataFrame(columns=columns)

    summary = (
        missing_df.groupby(COL_PRODUCT_CODE, as_index=False)
        .agg({COL_PRODUCT_NAME: "first", COL_OPERATOR_CODE: "first", COL_TXN_ID: "count"})
        .rename(columns={COL_TXN_ID: COL_TXN_COUNT})
    )
    return summary[columns]


def check_duplicate_mapping(mapping_df: pd.DataFrame) -> pd.DataFrame:
    """매핑표 내 상품코드 중복 등록을 찾는다."""
    dup_df = mapping_df[mapping_df.duplicated(subset=[COL_PRODUCT_CODE], keep=False)]
    return dup_df.sort_values(COL_PRODUCT_CODE).reset_index(drop=True)


def check_inactive_product_usage(raw_df: pd.DataFrame, mapping_df: pd.DataFrame) -> pd.DataFrame:
    """비활성 상품코드로 발생한 RAW 거래를 찾는다."""
    inactive_codes = set(mapping_df.loc[mapping_df[COL_USE_YN] == USE_YN_INACTIVE, COL_PRODUCT_CODE])
    usage_df = raw_df[raw_df[COL_PRODUCT_CODE].isin(inactive_codes)]

    columns = [COL_PRODUCT_CODE, COL_PRODUCT_NAME, COL_OPERATOR_CODE, COL_TXN_COUNT]
    if usage_df.empty:
        return pd.DataFrame(columns=columns)

    summary = (
        usage_df.groupby(COL_PRODUCT_CODE, as_index=False)
        .agg({COL_PRODUCT_NAME: "first", COL_OPERATOR_CODE: "first", COL_TXN_ID: "count"})
        .rename(columns={COL_TXN_ID: COL_TXN_COUNT})
    )
    return summary[columns]


def check_name_mismatch(
    raw_df: pd.DataFrame, portal_df: pd.DataFrame, mapping_df: pd.DataFrame
) -> pd.DataFrame:
    """동일 상품코드에 대해 RAW/포털/매핑표 상품명이 다른 케이스를 찾는다."""
    mapping_names = mapping_df.drop_duplicates(COL_PRODUCT_CODE).set_index(COL_PRODUCT_CODE)[
        COL_PRODUCT_NAME
    ]
    raw_names = raw_df.groupby(COL_PRODUCT_CODE)[COL_PRODUCT_NAME].agg(lambda s: sorted(set(s)))
    portal_names = portal_df.groupby(COL_PRODUCT_CODE)[COL_PRODUCT_NAME].agg(
        lambda s: sorted(set(s))
    )

    rows = []
    for product_code, mapping_name in mapping_names.items():
        raw_variants = raw_names.get(product_code, [])
        portal_variants = portal_names.get(product_code, [])

        all_names = {mapping_name, *raw_variants, *portal_variants}
        if len(all_names) > 1:
            rows.append(
                {
                    COL_PRODUCT_CODE: product_code,
                    COL_MAPPING_NAME: mapping_name,
                    COL_RAW_NAME: ", ".join(raw_variants) if raw_variants else "-",
                    COL_PORTAL_NAME: ", ".join(portal_variants) if portal_variants else "-",
                }
            )

    return pd.DataFrame(
        rows, columns=[COL_PRODUCT_CODE, COL_MAPPING_NAME, COL_RAW_NAME, COL_PORTAL_NAME]
    )


def run_all_validations(
    raw_df: pd.DataFrame, portal_df: pd.DataFrame, mapping_df: pd.DataFrame
) -> dict:
    """4가지 검증을 모두 실행하고 결과를 dict로 반환."""
    return {
        "매핑누락": check_missing_mapping(raw_df, mapping_df),
        "중복": check_duplicate_mapping(mapping_df),
        "비활성사용": check_inactive_product_usage(raw_df, mapping_df),
        "명칭불일치": check_name_mismatch(raw_df, portal_df, mapping_df),
    }
