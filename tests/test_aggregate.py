"""
aggregate.py 핵심 로직 테스트.
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
    STATUS_NEEDS_REVIEW,
    STATUS_OK,
    TXN_TYPE_CHURN,
    TXN_TYPE_NEW,
)
from src import aggregate, compare


def test_filter_current_month_keeps_only_target_month():
    raw_df = pd.DataFrame(
        {
            COL_TXN_DATE: ["2026-06-30", "2026-07-01", "2026-07-19", "2026-07-20"],
            COL_OPERATOR_CODE: ["MVN01"] * 4,
            COL_PRODUCT_CODE: ["A001"] * 4,
            COL_TXN_TYPE: [TXN_TYPE_NEW] * 4,
        }
    )

    result = aggregate.filter_current_month(raw_df, date(2026, 7, 19))

    assert list(result[COL_TXN_DATE]) == [date(2026, 7, 1), date(2026, 7, 19)]


def test_aggregate_by_operator_product_computes_net_count():
    monthly_df = pd.DataFrame(
        {
            COL_OPERATOR_CODE: ["MVN01", "MVN01", "MVN01"],
            COL_PRODUCT_CODE: ["A001", "A001", "A001"],
            COL_PRODUCT_NAME: ["상품A", "상품A", "상품A"],
            COL_TXN_TYPE: [TXN_TYPE_NEW, TXN_TYPE_NEW, TXN_TYPE_CHURN],
        }
    )

    result = aggregate.aggregate_by_operator_product(monthly_df)

    row = result.iloc[0]
    assert row[COL_NEW_COUNT] == 2
    assert row[COL_CHURN_COUNT] == 1
    assert row[COL_NET_COUNT] == 1


def test_aggregate_by_operator_sums_across_products():
    monthly_df = pd.DataFrame(
        {
            COL_OPERATOR_CODE: ["MVN01", "MVN01"],
            COL_PRODUCT_CODE: ["A001", "A002"],
            COL_PRODUCT_NAME: ["상품A", "상품B"],
            COL_TXN_TYPE: [TXN_TYPE_NEW, TXN_TYPE_NEW],
        }
    )

    result = aggregate.aggregate_by_operator(monthly_df)

    assert len(result) == 1
    assert result.iloc[0][aggregate.COL_CUMULATIVE_COUNT] == 2


def test_attach_validation_status_flags_operator_with_compare_issue():
    operator_summary_df = pd.DataFrame(
        {COL_OPERATOR_CODE: ["MVN01", "MVN02"], COL_OPERATOR_NAME: ["A사", "B사"]}
    )
    compare_df = pd.DataFrame(
        {COL_OPERATOR_CODE: ["MVN01"], compare.COL_ISSUE_FLAG: [True]}
    )
    validation_results = {"매핑누락": pd.DataFrame(columns=[COL_OPERATOR_CODE])}

    result = aggregate.attach_validation_status(operator_summary_df, compare_df, validation_results)

    status_by_code = dict(zip(result[COL_OPERATOR_CODE], result[COL_VALIDATION_STATUS]))
    assert status_by_code["MVN01"] == STATUS_NEEDS_REVIEW
    assert status_by_code["MVN02"] == STATUS_OK


def test_attach_validation_status_flags_operator_with_mapping_issue():
    operator_summary_df = pd.DataFrame(
        {COL_OPERATOR_CODE: ["MVN01", "MVN02"], COL_OPERATOR_NAME: ["A사", "B사"]}
    )
    compare_df = pd.DataFrame(columns=[COL_OPERATOR_CODE, compare.COL_ISSUE_FLAG])
    validation_results = {
        "매핑누락": pd.DataFrame({COL_OPERATOR_CODE: ["MVN02"]}),
    }

    result = aggregate.attach_validation_status(operator_summary_df, compare_df, validation_results)

    status_by_code = dict(zip(result[COL_OPERATOR_CODE], result[COL_VALIDATION_STATUS]))
    assert status_by_code["MVN01"] == STATUS_OK
    assert status_by_code["MVN02"] == STATUS_NEEDS_REVIEW
