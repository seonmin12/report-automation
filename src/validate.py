"""
매핑/데이터 정합성 검증 모듈 ('요금제 미매핑 현황' 대응).

RAW 데이터와 매핑 기준표를 대조하여 4가지 이슈를 검출한다.
1. 매핑 누락: RAW에는 있는데 매핑표에 없는 상품코드
2. 중복: 매핑표에 같은 상품코드가 두 번 이상 등록됨
3. 비활성 상품 사용: 매핑표 상 사용여부가 '비활성'인데 RAW에서 거래가 발생함
4. 상품명 불일치: 동일 상품코드에 대해 RAW/포털/매핑표의 상품명이 서로 다름
"""

import pandas as pd


def check_missing_mapping(raw_df: pd.DataFrame, mapping_df: pd.DataFrame) -> pd.DataFrame:
    """RAW에는 존재하지만 매핑표에 없는 상품코드를 찾는다.

    TODO: set(raw 상품코드) - set(mapping 상품코드)로 누락 목록 산출
    """
    raise NotImplementedError


def check_duplicate_mapping(mapping_df: pd.DataFrame) -> pd.DataFrame:
    """매핑표 내 상품코드 중복 등록을 찾는다.

    TODO: duplicated(subset=["상품코드"], keep=False)로 중복 행 추출
    """
    raise NotImplementedError


def check_inactive_product_usage(raw_df: pd.DataFrame, mapping_df: pd.DataFrame) -> pd.DataFrame:
    """비활성 상품코드로 발생한 RAW 거래를 찾는다.

    TODO: mapping_df에서 사용여부='비활성'인 상품코드 목록 추출 후 raw_df와 merge
    """
    raise NotImplementedError


def check_name_mismatch(
    raw_df: pd.DataFrame, portal_df: pd.DataFrame, mapping_df: pd.DataFrame
) -> pd.DataFrame:
    """동일 상품코드에 대해 RAW/포털/매핑표 상품명이 다른 케이스를 찾는다.

    TODO: 상품코드 기준으로 세 데이터의 상품명을 모아 비교, 불일치 행만 추출
    """
    raise NotImplementedError


def run_all_validations(
    raw_df: pd.DataFrame, portal_df: pd.DataFrame, mapping_df: pd.DataFrame
) -> dict:
    """4가지 검증을 모두 실행하고 결과를 dict로 반환.

    TODO: 각 check_* 함수를 호출하여
    {"매핑누락": df, "중복": df, "비활성사용": df, "명칭불일치": df} 형태로 반환
    """
    raise NotImplementedError
