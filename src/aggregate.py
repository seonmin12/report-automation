"""
당월 누적 실적 집계 모듈.

RAW 거래 데이터를 기준일(as_of_date) 기준으로 당월 1일부터 기준일까지 필터링하고,
사업자/상품 단위로 신규/해지/순증 건수를 집계한다.
'과기부 제출자료(사업자별 누적가입자)'는 이 집계 결과를 사업자 단위로 한 번 더 묶어서 만든다.
"""

from datetime import date

import pandas as pd


def filter_current_month(raw_df: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """기준일이 속한 달의 1일부터 기준일까지 데이터만 필터링.

    TODO: 처리일자 컬럼을 datetime으로 변환 후 조건 필터
    """
    raise NotImplementedError


def aggregate_by_operator_product(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """사업자/상품 단위로 신규/해지/순증 건수 집계.

    TODO: groupby(["사업자코드", "상품코드"]) 후 거래유형별 건수 pivot,
    순증 = 신규 - 해지 계산
    """
    raise NotImplementedError


def aggregate_by_operator(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """사업자 단위 누적 가입자 집계 (과기부 제출자료 포맷).

    TODO: groupby(["사업자코드", "사업자명"])로 누적가입자수(순증 합계) 계산
    """
    raise NotImplementedError
