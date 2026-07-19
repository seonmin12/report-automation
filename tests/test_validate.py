"""
validate.py 검증 로직 테스트.

각 검증 함수에 대해 '이슈가 있는 케이스'와 '이슈가 없는 케이스'를 작은
DataFrame으로 직접 만들어 테스트한다 (더미데이터 생성기에 의존하지 않음).
"""

import pandas as pd

from config import (
    COL_OPERATOR_CODE,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_TXN_ID,
    COL_USE_YN,
    USE_YN_ACTIVE,
    USE_YN_INACTIVE,
)
from src import validate


def test_check_missing_mapping_detects_unmapped_product():
    """RAW에는 있지만 매핑표에 없는 상품코드가 검출되는지 확인."""
    mapping_df = pd.DataFrame(
        {
            COL_PRODUCT_CODE: ["A001", "A002"],
            COL_PRODUCT_NAME: ["상품A", "상품B"],
            COL_USE_YN: [USE_YN_ACTIVE, USE_YN_ACTIVE],
        }
    )
    raw_df = pd.DataFrame(
        {
            COL_TXN_ID: ["T1", "T2", "T3"],
            COL_PRODUCT_CODE: ["A001", "B999", "B999"],
            COL_PRODUCT_NAME: ["상품A", "미확인상품", "미확인상품"],
            COL_OPERATOR_CODE: ["MVN01", "MVN02", "MVN02"],
        }
    )

    result = validate.check_missing_mapping(raw_df, mapping_df)

    assert set(result[COL_PRODUCT_CODE]) == {"B999"}
    assert result.loc[result[COL_PRODUCT_CODE] == "B999", validate.COL_TXN_COUNT].iloc[0] == 2


def test_check_missing_mapping_no_issue_when_all_mapped():
    mapping_df = pd.DataFrame(
        {COL_PRODUCT_CODE: ["A001"], COL_PRODUCT_NAME: ["상품A"], COL_USE_YN: [USE_YN_ACTIVE]}
    )
    raw_df = pd.DataFrame(
        {
            COL_TXN_ID: ["T1"],
            COL_PRODUCT_CODE: ["A001"],
            COL_PRODUCT_NAME: ["상품A"],
            COL_OPERATOR_CODE: ["MVN01"],
        }
    )

    result = validate.check_missing_mapping(raw_df, mapping_df)

    assert result.empty


def test_check_duplicate_mapping_detects_duplicate_code():
    """매핑표 내 상품코드 중복이 검출되는지 확인."""
    mapping_df = pd.DataFrame(
        {
            COL_PRODUCT_CODE: ["A001", "A001", "A002"],
            COL_PRODUCT_NAME: ["상품A", "상품A", "상품B"],
            COL_USE_YN: [USE_YN_ACTIVE, USE_YN_ACTIVE, USE_YN_ACTIVE],
        }
    )

    result = validate.check_duplicate_mapping(mapping_df)

    assert set(result[COL_PRODUCT_CODE]) == {"A001"}
    assert len(result) == 2


def test_check_duplicate_mapping_no_issue_when_unique():
    mapping_df = pd.DataFrame(
        {
            COL_PRODUCT_CODE: ["A001", "A002"],
            COL_PRODUCT_NAME: ["상품A", "상품B"],
            COL_USE_YN: [USE_YN_ACTIVE, USE_YN_ACTIVE],
        }
    )

    result = validate.check_duplicate_mapping(mapping_df)

    assert result.empty


def test_check_inactive_product_usage_detects_inactive_usage():
    """비활성 상품코드 사용이 검출되는지 확인."""
    mapping_df = pd.DataFrame(
        {
            COL_PRODUCT_CODE: ["A001", "A002"],
            COL_PRODUCT_NAME: ["상품A", "상품B"],
            COL_USE_YN: [USE_YN_ACTIVE, USE_YN_INACTIVE],
        }
    )
    raw_df = pd.DataFrame(
        {
            COL_TXN_ID: ["T1", "T2"],
            COL_PRODUCT_CODE: ["A001", "A002"],
            COL_PRODUCT_NAME: ["상품A", "상품B"],
            COL_OPERATOR_CODE: ["MVN01", "MVN01"],
        }
    )

    result = validate.check_inactive_product_usage(raw_df, mapping_df)

    assert set(result[COL_PRODUCT_CODE]) == {"A002"}
    assert result.loc[result[COL_PRODUCT_CODE] == "A002", validate.COL_TXN_COUNT].iloc[0] == 1


def test_check_inactive_product_usage_no_issue_when_all_active():
    mapping_df = pd.DataFrame(
        {
            COL_PRODUCT_CODE: ["A001"],
            COL_PRODUCT_NAME: ["상품A"],
            COL_USE_YN: [USE_YN_ACTIVE],
        }
    )
    raw_df = pd.DataFrame(
        {
            COL_TXN_ID: ["T1"],
            COL_PRODUCT_CODE: ["A001"],
            COL_PRODUCT_NAME: ["상품A"],
            COL_OPERATOR_CODE: ["MVN01"],
        }
    )

    result = validate.check_inactive_product_usage(raw_df, mapping_df)

    assert result.empty


def test_check_name_mismatch_detects_different_names():
    """동일 상품코드의 상품명 불일치가 검출되는지 확인."""
    mapping_df = pd.DataFrame(
        {COL_PRODUCT_CODE: ["A001", "A002"], COL_PRODUCT_NAME: ["표준상품A", "표준상품B"]}
    )
    raw_df = pd.DataFrame(
        {
            COL_PRODUCT_CODE: ["A001", "A001", "A002"],
            COL_PRODUCT_NAME: ["표준상품A", "변경된상품A", "표준상품B"],
        }
    )
    portal_df = pd.DataFrame(
        {COL_PRODUCT_CODE: ["A001", "A002"], COL_PRODUCT_NAME: ["표준상품A", "표준상품B"]}
    )

    result = validate.check_name_mismatch(raw_df, portal_df, mapping_df)

    assert set(result[COL_PRODUCT_CODE]) == {"A001"}
    row = result.loc[result[COL_PRODUCT_CODE] == "A001"].iloc[0]
    assert row[validate.COL_MAPPING_NAME] == "표준상품A"
    assert "변경된상품A" in row[validate.COL_RAW_NAME]


def test_check_name_mismatch_no_issue_when_names_consistent():
    mapping_df = pd.DataFrame({COL_PRODUCT_CODE: ["A001"], COL_PRODUCT_NAME: ["표준상품A"]})
    raw_df = pd.DataFrame({COL_PRODUCT_CODE: ["A001"], COL_PRODUCT_NAME: ["표준상품A"]})
    portal_df = pd.DataFrame({COL_PRODUCT_CODE: ["A001"], COL_PRODUCT_NAME: ["표준상품A"]})

    result = validate.check_name_mismatch(raw_df, portal_df, mapping_df)

    assert result.empty
