"""
Teams 공유용 요약 이미지(PNG) 생성 모듈.

실무에서 엑셀 화면을 캡처해 비트맵으로 Teams에 붙여넣던 방식을 재현한다.
matplotlib의 table 기능으로 핵심 요약표를 이미지로 렌더링한다.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

# 한글이 네모(tofu)로 깨지지 않도록, 시스템에 설치된 한글 폰트를 우선 사용
_KOREAN_FONT_CANDIDATES = ["AppleGothic", "Malgun Gothic", "NanumGothic", "Noto Sans CJK KR"]


def _apply_korean_font():
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _KOREAN_FONT_CANDIDATES:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


_apply_korean_font()


def build_summary_image(summary_df: pd.DataFrame, output_path, title: str = "실적 검증 요약"):
    """요약 DataFrame을 표 이미지(PNG)로 렌더링."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n_rows, n_cols = summary_df.shape
    fig_width = max(6.0, 1.6 * n_cols)
    fig_height = max(2.0, 0.5 + 0.45 * (n_rows + 1))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=14)

    table = ax.table(
        cellText=summary_df.astype(str).values.tolist(),
        colLabels=summary_df.columns.tolist(),
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)

    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
