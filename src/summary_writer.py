"""
Teams/이메일용 텍스트 요약 생성 모듈.

검증 결과를 사람이 바로 읽고 복사-붙여넣기 할 수 있는 짧은 텍스트로 변환한다.
"""

from datetime import date

import pandas as pd


def build_text_summary(
    as_of_date: date,
    compare_df: pd.DataFrame,
    validation_results: dict,
    operator_summary_df: pd.DataFrame,
) -> str:
    """검증 결과를 텍스트 요약문으로 변환.

    TODO: 아래와 같은 형태로 문자열 조립
    [실적 검증 요약 - 2026.07.19 기준]
    - 실적 비교: 이상 N건 (임계치 초과)
    - 요금제 미매핑: N건 / 중복: N건 / 비활성상품 사용: N건 / 명칭불일치: N건
    - 사업자별 누적가입자: (사업자명별 요약 1~2줄)
    ※ 상세 내역은 첨부 엑셀 참고
    """
    raise NotImplementedError


def save_text_summary(text: str, output_path):
    """텍스트 요약을 .txt 파일로 저장.

    TODO: output_path.write_text(text, encoding="utf-8")
    """
    raise NotImplementedError
