"""
Excel 검증 리포트 생성 모듈.

openpyxl을 사용해 실무형 엑셀 리포트를 만든다. 시트 구성:
1. 요약 (전체 이슈 건수, 실적 차이 개요)
2. 실적비교 (compare.py 결과 - 실시간 실적 공지 대응)
3. 요금제미매핑이슈 (validate.py 결과 4종 통합 - 요금제 미매핑 현황 대응)
4. 사업자별누적가입자 (aggregate.py 결과 - 과기부 제출자료 대응)

이상 항목은 조건부 서식(빨간 배경 등)으로 강조한다.
"""

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

from .aggregate import COL_CUMULATIVE_COUNT
from .compare import COL_ISSUE_FLAG

ISSUE_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)

DEFAULT_COLUMN_WIDTH = 16


def write_dataframe_to_sheet(ws, df: pd.DataFrame, highlight_col: str | None = None):
    """DataFrame을 워크시트에 쓰고 헤더 스타일 적용.

    highlight_col이 주어지면 해당 컬럼 값이 참(True)인 행에 ISSUE_FILL을 적용한다.
    """
    columns = list(df.columns)
    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)

    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    highlight_col_idx = None
    if highlight_col is not None and highlight_col in columns:
        highlight_col_idx = columns.index(highlight_col) + 1

    if highlight_col_idx is not None:
        for row_idx in range(2, ws.max_row + 1):
            if bool(ws.cell(row=row_idx, column=highlight_col_idx).value):
                for cell in ws[row_idx]:
                    cell.fill = ISSUE_FILL

    for col_idx in range(1, len(columns) + 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = (
            DEFAULT_COLUMN_WIDTH
        )


def _write_summary_sheet(
    ws,
    compare_df: pd.DataFrame,
    validation_results: dict,
    operator_summary_df: pd.DataFrame,
):
    ws["A1"] = "실적 검증 요약"
    ws["A1"].font = Font(bold=True, size=14)

    ws.append([])
    ws.append(["항목", "건수"])
    for cell in ws[3]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    compare_issue_count = int(compare_df[COL_ISSUE_FLAG].sum()) if not compare_df.empty else 0
    ws.append(["실적 비교 이상 (임계치 초과 / 한쪽에만 존재)", compare_issue_count])
    for name, df in validation_results.items():
        ws.append([f"요금제 미매핑 - {name}", len(df)])

    total_subscribers = (
        int(operator_summary_df[COL_CUMULATIVE_COUNT].sum()) if not operator_summary_df.empty else 0
    )
    ws.append(["사업자 전체 누적가입자수", total_subscribers])

    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 16


def _write_validation_issues_sheet(ws, validation_results: dict):
    current_row = 1
    for name, df in validation_results.items():
        title_cell = ws.cell(row=current_row, column=1, value=f"{name} ({len(df)}건)")
        title_cell.font = Font(bold=True)
        current_row += 1

        if df.empty:
            ws.cell(row=current_row, column=1, value="해당 없음")
            current_row += 2
            continue

        for col_idx, col_name in enumerate(df.columns, start=1):
            cell = ws.cell(row=current_row, column=col_idx, value=col_name)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
        current_row += 1

        for _, values in df.iterrows():
            for col_idx, value in enumerate(values, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=value)
                cell.fill = ISSUE_FILL
            current_row += 1

        current_row += 1  # 섹션 간 빈 줄

    for col_idx in range(1, 8):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = (
            DEFAULT_COLUMN_WIDTH
        )


def build_excel_report(
    compare_df: pd.DataFrame,
    validation_results: dict,
    operator_summary_df: pd.DataFrame,
    output_path,
):
    """4개 시트로 구성된 검증 리포트 엑셀 생성."""
    wb = Workbook()

    summary_ws = wb.active
    summary_ws.title = "요약"
    _write_summary_sheet(summary_ws, compare_df, validation_results, operator_summary_df)

    compare_ws = wb.create_sheet("실적비교")
    write_dataframe_to_sheet(compare_ws, compare_df, highlight_col=COL_ISSUE_FLAG)

    issue_ws = wb.create_sheet("요금제미매핑이슈")
    _write_validation_issues_sheet(issue_ws, validation_results)

    operator_ws = wb.create_sheet("사업자별누적가입자")
    write_dataframe_to_sheet(operator_ws, operator_summary_df)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
