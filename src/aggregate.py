"""
당월 누적 실적 집계 모듈.

RAW 거래 데이터를 기준일(as_of_date) 기준으로 당월 1일부터 기준일까지 필터링하고,
사업자/상품 단위로 신규/해지/순증 건수를 집계한다.
'과기부 제출자료(사업자별 누적가입자)'는 이 집계 결과를 사업자 단위로 한 번 더 묶어서 만든다.
"""

from datetime import date

import pandas as pd

from config import (
    COL_CHURN_COUNT,
    COL_NET_COUNT,
    COL_NEW_COUNT,
    COL_OPERATOR_CODE,
    COL_OPERATOR_NAME,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_TXN_DATE,
    COL_TXN_TYPE,
    COL_VALIDATION_STATUS,
    DUMMY_OPERATORS,
    STATUS_NEEDS_REVIEW,
    STATUS_OK,
    TXN_TYPE_CHURN,
    TXN_TYPE_NEW,
)

from .compare import COL_ISSUE_FLAG

# 사업자 단위 집계 전용 컬럼명
COL_CUMULATIVE_COUNT = "누적가입자수"

_OPERATOR_NAME_MAP = {op[COL_OPERATOR_CODE]: op[COL_OPERATOR_NAME] for op in DUMMY_OPERATORS}


def filter_current_month(raw_df: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """기준일이 속한 달의 1일부터 기준일까지 데이터만 필터링."""
    df = raw_df.copy()
    df[COL_TXN_DATE] = pd.to_datetime(df[COL_TXN_DATE]).dt.date

    month_start = as_of_date.replace(day=1)
    mask = (df[COL_TXN_DATE] >= month_start) & (df[COL_TXN_DATE] <= as_of_date)
    return df[mask].reset_index(drop=True)


def aggregate_by_operator_product(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """사업자/상품 단위로 신규/해지/순증 건수 집계."""
    pivot = (
        monthly_df.groupby([COL_OPERATOR_CODE, COL_PRODUCT_CODE, COL_TXN_TYPE])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for txn_type in (TXN_TYPE_NEW, TXN_TYPE_CHURN):
        if txn_type not in pivot.columns:
            pivot[txn_type] = 0

    pivot = pivot.rename(columns={TXN_TYPE_NEW: COL_NEW_COUNT, TXN_TYPE_CHURN: COL_CHURN_COUNT})
    pivot[COL_NET_COUNT] = pivot[COL_NEW_COUNT] - pivot[COL_CHURN_COUNT]
    pivot[COL_OPERATOR_NAME] = pivot[COL_OPERATOR_CODE].map(_OPERATOR_NAME_MAP)

    # 사업자/상품 조합에서 가장 많이 등장한 상품명을 대표값으로 사용
    product_name = (
        monthly_df.groupby([COL_OPERATOR_CODE, COL_PRODUCT_CODE])[COL_PRODUCT_NAME]
        .agg(lambda s: s.value_counts().idxmax())
        .reset_index()
    )

    result = pivot.merge(product_name, on=[COL_OPERATOR_CODE, COL_PRODUCT_CODE], how="left")
    return result[
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


def aggregate_by_operator(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """사업자 단위 누적 가입자 집계 (과기부 제출자료 포맷)."""
    operator_product_df = aggregate_by_operator_product(monthly_df)

    summary = operator_product_df.groupby(
        [COL_OPERATOR_CODE, COL_OPERATOR_NAME], as_index=False
    )[[COL_NEW_COUNT, COL_CHURN_COUNT, COL_NET_COUNT]].sum()

    summary = summary.rename(columns={COL_NET_COUNT: COL_CUMULATIVE_COUNT})
    return summary[
        [COL_OPERATOR_CODE, COL_OPERATOR_NAME, COL_NEW_COUNT, COL_CHURN_COUNT, COL_CUMULATIVE_COUNT]
    ]


def attach_validation_status(
    operator_summary_df: pd.DataFrame,
    compare_df: pd.DataFrame,
    validation_results: dict,
) -> pd.DataFrame:
    """사업자별 요약에 검증상태(정상/확인필요) 컬럼을 추가.

    실적비교 이상 항목 또는 매핑 이슈 4종 중 하나라도 걸린 사업자는 '확인필요'로 표시한다.
    CLI(main.py)와 웹 대시보드(web/app.py) 양쪽에서 동일하게 재사용한다.
    """
    flagged_operators = set()

    if not compare_df.empty:
        flagged_operators.update(compare_df.loc[compare_df[COL_ISSUE_FLAG], COL_OPERATOR_CODE])

    for df in validation_results.values():
        if COL_OPERATOR_CODE in df.columns:
            flagged_operators.update(df[COL_OPERATOR_CODE])

    result = operator_summary_df.copy()
    result[COL_VALIDATION_STATUS] = result[COL_OPERATOR_CODE].apply(
        lambda code: STATUS_NEEDS_REVIEW if code in flagged_operators else STATUS_OK
    )
    return result
