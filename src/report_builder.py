"""
Excel 검증 리포트 생성 모듈.

openpyxl을 사용해 실무형 엑셀 리포트를 만든다. 시트 구성:
1. 요약 (전체 이슈 건수, 실적 차이 개요)
2. 실적비교 (compare.py 결과 - 실시간 실적 공지 대응)
3. 요금제미매핑이슈 (validate.py 결과 4종 통합 - 요금제 미매핑 현황 대응)
4. 사업자별누적가입자 (aggregate.py 결과 - 과기부 제출자료 대응)

이상 항목은 조건부 서식(빨간 배경 등)으로 강조한다.
"""

import pandas as pd
from openpyxl.styles import PatternFill, Font
from openpyxl.utils.dataframe import dataframe_to_rows


ISSUE_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def write_dataframe_to_sheet(ws, df: pd.DataFrame, highlight_col: str | None = None):
    """DataFrame을 워크시트에 쓰고 헤더 스타일 적용.

    TODO:
    - dataframe_to_rows로 값 채우기
    - 1행 헤더에 HEADER_FILL/HEADER_FONT 적용
    - highlight_col이 있으면 해당 값이 True/이상인 행에 ISSUE_FILL 적용
    """
    raise NotImplementedError


def build_excel_report(
    compare_df: pd.DataFrame,
    validation_results: dict,
    operator_summary_df: pd.DataFrame,
    output_path,
):
    """4개 시트로 구성된 검증 리포트 엑셀 생성.

    TODO: openpyxl.Workbook() 생성 후 시트별로 write_dataframe_to_sheet 호출, save
    """
    raise NotImplementedError
