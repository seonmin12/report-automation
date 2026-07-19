"""
Teams/이메일용 텍스트 요약 생성 모듈.

검증 결과를 사람이 바로 읽고 복사-붙여넣기 할 수 있는 짧은 텍스트로 변환한다.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from config import COL_OPERATOR_NAME

from .aggregate import COL_CUMULATIVE_COUNT
from .compare import COL_ISSUE_FLAG, DIFF_THRESHOLD_PCT


def build_text_summary(
    as_of_date: date,
    compare_df: pd.DataFrame,
    validation_results: dict,
    operator_summary_df: pd.DataFrame,
) -> str:
    """검증 결과를 텍스트 요약문으로 변환."""
    compare_issue_count = int(compare_df[COL_ISSUE_FLAG].sum()) if not compare_df.empty else 0

    issue_summary = " / ".join(f"{name} {len(df)}건" for name, df in validation_results.items())

    lines = [
        f"[실적 검증 요약 - {as_of_date.strftime('%Y.%m.%d')} 기준]",
        f"- 실적 비교: 이상 {compare_issue_count}건 (임계치 {DIFF_THRESHOLD_PCT}% 초과 또는 한쪽에만 존재)",
        f"- 요금제 미매핑: {issue_summary}",
        "- 사업자별 누적가입자:",
    ]
    for _, row in operator_summary_df.iterrows():
        lines.append(f"  · {row[COL_OPERATOR_NAME]}: {row[COL_CUMULATIVE_COUNT]:,}명")

    lines.append("※ 상세 내역은 첨부 엑셀 참고")
    return "\n".join(lines)


def save_text_summary(text: str, output_path):
    """텍스트 요약을 .txt 파일로 저장."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
