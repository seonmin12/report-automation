"""
포털 집계값 vs RAW 집계값 비교 모듈 ('실시간 실적 공지' 대응).

포털에서 내려받은 실적(집계값)과, RAW 데이터를 직접 집계한 값을 merge하여
사업자/상품 단위로 차이(건수, %)를 계산하고 임계치를 벗어나는 항목을 표시한다.
"""

import pandas as pd

# 차이 판정 임계치 (이 값 이상 벗어나면 '이상' 플래그)
DIFF_THRESHOLD_PCT = 1.0  # %


def compare_portal_vs_raw(
    portal_df: pd.DataFrame, raw_agg_df: pd.DataFrame
) -> pd.DataFrame:
    """포털 실적과 RAW 집계값을 사업자/상품 기준으로 merge하여 비교.

    TODO:
    - outer merge (사업자코드, 상품코드 기준)
    - 차이(diff) = 포털값 - RAW값, 차이율(%) 계산
    - DIFF_THRESHOLD_PCT 초과 항목에 '이상여부' 플래그 추가
    - 한쪽에만 존재하는 상품(포털에만 있음 / RAW에만 있음)도 표시
    """
    raise NotImplementedError
