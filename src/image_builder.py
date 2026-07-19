"""
Teams 공유용 요약 이미지(PNG) 생성 모듈.

실무에서 엑셀 화면을 캡처해 비트맵으로 Teams에 붙여넣던 방식을 재현한다.
matplotlib의 table 기능으로 핵심 요약표를 이미지로 렌더링한다.
"""

import pandas as pd
import matplotlib.pyplot as plt


def build_summary_image(summary_df: pd.DataFrame, output_path, title: str = "실적 검증 요약"):
    """요약 DataFrame을 표 이미지(PNG)로 렌더링.

    TODO:
    - fig, ax = plt.subplots() 생성, axis off
    - ax.table(cellText=..., colLabels=..., loc="center")로 표 렌더링
    - title을 상단에 표시
    - plt.savefig(output_path, dpi=200, bbox_inches="tight")
    """
    raise NotImplementedError
