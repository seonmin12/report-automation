"""
validate.py 검증 로직 테스트.

각 검증 함수에 대해 '이슈가 있는 케이스'와 '이슈가 없는 케이스'를 작은
DataFrame으로 직접 만들어 테스트한다 (더미데이터 생성기에 의존하지 않음).
"""

import pandas as pd
import pytest

from src import validate


def test_check_missing_mapping_detects_unmapped_product():
    """RAW에는 있지만 매핑표에 없는 상품코드가 검출되는지 확인.

    TODO: raw_df, mapping_df를 직접 구성해서
    validate.check_missing_mapping(raw_df, mapping_df) 결과에
    누락 상품코드가 포함되는지 assert
    """
    pass  # TODO


def test_check_duplicate_mapping_detects_duplicate_code():
    """매핑표 내 상품코드 중복이 검출되는지 확인.

    TODO
    """
    pass  # TODO


def test_check_inactive_product_usage_detects_inactive_usage():
    """비활성 상품코드 사용이 검출되는지 확인.

    TODO
    """
    pass  # TODO


def test_check_name_mismatch_detects_different_names():
    """동일 상품코드의 상품명 불일치가 검출되는지 확인.

    TODO
    """
    pass  # TODO
