"""
포털 집계값 vs RAW 집계값 비교 모듈 ('실시간 실적 공지' 대응).

포털에서 내려받은 실적(집계값)과, RAW 데이터를 직접 집계한 값을 merge하여
사업자/상품 단위로 차이(건수, %)를 계산하고 임계치를 벗어나는 항목을 표시한다.
"""

import numpy as np
import pandas as pd

from config import (
    COL_CHURN_COUNT,
    COL_NET_COUNT,
    COL_NEW_COUNT,
    COL_OPERATOR_CODE,
    COL_OPERATOR_NAME,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_VALIDATION_STATUS,
    STATUS_NEEDS_REVIEW,
    STATUS_OK,
)

# 차이 판정 임계치 (이 값 이상 벗어나면 '이상' 플래그)
DIFF_THRESHOLD_PCT = 1.0  # %

_PORTAL_SUFFIX = "_포털"
_RAW_SUFFIX = "_RAW"

COL_DIFF = "차이"
COL_DIFF_PCT = "차이율(%)"
COL_SOURCE = "존재출처"
COL_ISSUE_FLAG = "이상여부"

SOURCE_PORTAL_ONLY = "포털에만 존재"
SOURCE_RAW_ONLY = "RAW에만 존재"
SOURCE_BOTH = "양쪽 존재"


def compare_portal_vs_raw(portal_df: pd.DataFrame, raw_agg_df: pd.DataFrame) -> pd.DataFrame:
    """포털 실적과 RAW 집계값을 사업자/상품 기준으로 merge하여 비교."""
    merged = portal_df.merge(
        raw_agg_df,
        on=[COL_OPERATOR_CODE, COL_PRODUCT_CODE],
        how="outer",
        suffixes=(_PORTAL_SUFFIX, _RAW_SUFFIX),
        indicator=True,
    )

    # 사업자명은 한쪽에만 존재하는 상품이어도 값이 같으므로 하나로 합친다.
    merged[COL_OPERATOR_NAME] = merged[f"{COL_OPERATOR_NAME}{_PORTAL_SUFFIX}"].combine_first(
        merged[f"{COL_OPERATOR_NAME}{_RAW_SUFFIX}"]
    )

    count_cols = (COL_NEW_COUNT, COL_CHURN_COUNT, COL_NET_COUNT)
    for col in count_cols:
        merged[f"{col}{_PORTAL_SUFFIX}"] = merged[f"{col}{_PORTAL_SUFFIX}"].fillna(0).astype(int)
        merged[f"{col}{_RAW_SUFFIX}"] = merged[f"{col}{_RAW_SUFFIX}"].fillna(0).astype(int)

    merged[COL_DIFF] = merged[f"{COL_NET_COUNT}{_PORTAL_SUFFIX}"] - merged[f"{COL_NET_COUNT}{_RAW_SUFFIX}"]
    raw_net = merged[f"{COL_NET_COUNT}{_RAW_SUFFIX}"].astype(float).replace(0, np.nan)
    merged[COL_DIFF_PCT] = (merged[COL_DIFF] / raw_net * 100).abs().fillna(0).round(2)

    merged[COL_SOURCE] = merged["_merge"].map(
        {"left_only": SOURCE_PORTAL_ONLY, "right_only": SOURCE_RAW_ONLY, "both": SOURCE_BOTH}
    )
    merged[COL_ISSUE_FLAG] = (merged[COL_DIFF_PCT] > DIFF_THRESHOLD_PCT) | (
        merged[COL_SOURCE] != SOURCE_BOTH
    )
    merged[COL_VALIDATION_STATUS] = merged[COL_ISSUE_FLAG].map(
        {True: STATUS_NEEDS_REVIEW, False: STATUS_OK}
    )

    columns = (
        [COL_OPERATOR_CODE, COL_OPERATOR_NAME, COL_PRODUCT_CODE]
        + [f"{COL_PRODUCT_NAME}{_PORTAL_SUFFIX}", f"{COL_PRODUCT_NAME}{_RAW_SUFFIX}"]
        + [f"{col}{_PORTAL_SUFFIX}" for col in count_cols]
        + [f"{col}{_RAW_SUFFIX}" for col in count_cols]
        + [COL_DIFF, COL_DIFF_PCT, COL_SOURCE, COL_ISSUE_FLAG, COL_VALIDATION_STATUS]
    )
    return merged[columns].sort_values(COL_DIFF_PCT, ascending=False).reset_index(drop=True)
