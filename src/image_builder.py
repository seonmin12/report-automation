"""
Teams 공유용 요약 이미지(PNG) 생성 모듈.

실무에서 엑셀 화면을 캡처해 비트맵으로 Teams에 붙여넣던 방식을 재현한다.
matplotlib의 table 기능으로 핵심 요약표를 이미지로 렌더링한다.
"""

from pathlib import Path

import matplotlib

# 화면에 띄우지 않고 파일로만 저장하므로 항상 non-interactive 백엔드를 쓴다.
# GUI 백엔드(예: macOS의 MacOSX)는 메인 스레드 밖(웹 서버 워커 스레드 등)에서 호출되면 에러가 난다.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from config import COL_VALIDATION_STATUS, STATUS_NEEDS_REVIEW

# 시스템에 설치된 한글 폰트 이름에 의존하면 Vercel 서버리스(Linux, 한글 폰트 미설치) 환경에서
# 한글이 네모(tofu)로 깨진다. OS와 무관하게 항상 동작하도록 폰트 파일을 리포에 직접 번들해서 쓴다.
_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NanumGothic-Regular.ttf"


def _apply_korean_font():
    font_manager.fontManager.addfont(str(_FONT_PATH))
    font_name = font_manager.FontProperties(fname=str(_FONT_PATH)).get_name()
    plt.rcParams["font.family"] = font_name
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

    if COL_VALIDATION_STATUS in summary_df.columns:
        status_col_idx = summary_df.columns.get_loc(COL_VALIDATION_STATUS)
        for row_idx, status in enumerate(summary_df[COL_VALIDATION_STATUS], start=1):
            if status == STATUS_NEEDS_REVIEW:
                table[row_idx, status_col_idx].set_text_props(color="#C00000", weight="bold")

    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
