"""
청크 처리 실험 오케스트레이터.

1. 정확성: chunked_check.py의 두 함수가 원본 validate.py 함수와 완전히 같은
   결과를 내는지 직접 대조 (DataFrame 단위, 그리고 ground_truth.json 단위 둘 다).
2. 성능: "raw_df를 통째로 읽어서 원본 함수 호출" vs "파일에서 청크로 스트리밍"을
   각각 독립 프로세스로 실행해서 이 두 검증만의 소요시간·피크 메모리를 잰다.

주의: 이건 전체 파이프라인이 아니라 매핑누락+비활성사용 두 검증만 떼어낸
실험이다 (chunked_check.py 상단 docstring에 이유 설명). 전체 파이프라인
피크 메모리는 이 최적화로 줄지 않는다 — 다른 검증(명칭불일치)과 집계
단계가 어차피 raw_df 전체를 필요로 하기 때문.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DEFAULT_AS_OF_DATE
from src import validate

from benchmark import chunked_check
from benchmark.run_benchmark import DEFAULT_SCALES, ensure_data

REPO_ROOT = Path(__file__).resolve().parent.parent
TRIAL_SCRIPT = Path(__file__).resolve().parent / "_trial_chunk.py"
CHUNKSIZE = 20_000


def verify_correctness(data_dir: Path) -> dict:
    """chunked_check.py 결과가 원본 validate.py 결과와 완전히 같은지 직접 대조."""
    mapping_df = pd.read_excel(data_dir / "product_mapping.xlsx")
    raw_df = pd.read_csv(data_dir / "raw_transactions.csv", encoding="utf-8-sig")

    orig_missing = validate.check_missing_mapping(raw_df, mapping_df)
    orig_inactive = validate.check_inactive_product_usage(raw_df, mapping_df)

    chunked_missing = chunked_check.check_missing_mapping_chunked(
        data_dir / "raw_transactions.csv", mapping_df, CHUNKSIZE
    )
    chunked_inactive = chunked_check.check_inactive_product_usage_chunked(
        data_dir / "raw_transactions.csv", mapping_df, CHUNKSIZE
    )

    def _normalize(df):
        return (
            df.astype(str)
            .sort_values("상품코드")
            .reset_index(drop=True)
        )

    missing_equal = _normalize(orig_missing).equals(_normalize(chunked_missing))
    inactive_equal = _normalize(orig_inactive).equals(_normalize(chunked_inactive))

    return {
        "missing_mapping_identical": missing_equal,
        "inactive_usage_identical": inactive_equal,
        "all_identical": missing_equal and inactive_equal,
    }


def run_isolated(mode: str, data_dir: Path, timeout_sec: int = 300) -> dict:
    proc = subprocess.run(
        [sys.executable, str(TRIAL_SCRIPT), "--data-dir", str(data_dir), "--mode", mode,
         "--chunksize", str(CHUNKSIZE)],
        capture_output=True, text=True, timeout=timeout_sec,
    )
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    return json.loads(lines[-1])


def main():
    scales = DEFAULT_SCALES
    seed = 42
    asof = str(DEFAULT_AS_OF_DATE)

    rows_data = []
    for rows in scales:
        print(f"\n=== {rows:,}행 ===")
        data_dir = ensure_data(rows, seed, asof)

        print("정확성 검증 중 (원본 vs 청크 스트리밍)...")
        correctness = verify_correctness(data_dir)
        print(f"  매핑누락 일치: {correctness['missing_mapping_identical']}, "
              f"비활성사용 일치: {correctness['inactive_usage_identical']}")

        print("성능 측정 중 (독립 프로세스, full vs chunked)...")
        full_result = run_isolated("full", data_dir)
        chunked_result = run_isolated("chunked", data_dir)
        print(f"  full: {full_result['load_seconds'] + full_result['check_seconds']:.4f}s, "
              f"RSS {full_result['memory']['rss_peak_mb']}MB")
        print(f"  chunked: {chunked_result['check_seconds']:.4f}s, "
              f"RSS {chunked_result['memory']['rss_peak_mb']}MB")

        rows_data.append({
            "rows": rows,
            "correctness": correctness,
            "full": full_result,
            "chunked": chunked_result,
        })

    md_lines = ["# 청크 처리 실험 결과\n"]
    md_lines.append(
        "**범위**: 매핑누락(`check_missing_mapping`) + 비활성사용(`check_inactive_product_usage`) "
        "두 검증만 독립적으로 뗀 실험입니다. 이 프로젝트의 실제 파이프라인에서는 "
        "다른 검증(명칭불일치)과 집계 단계가 어차피 RAW 전체를 메모리에 올려야 하므로, "
        "이 최적화가 **전체 파이프라인의 피크 메모리를 줄이지는 않습니다.** "
        "\"이 두 검증만 먼저 훑어야 하는 상황\" 또는 \"RAW가 메모리에 다 못 올라갈 만큼 "
        "훨씬 큰 경우\"를 가정한 결과로 읽어주세요.\n"
    )

    md_lines.append("## 정확성 (원본 vs 청크 스트리밍, 완전 동일한가)\n")
    md_lines.append("| 행 수 | 매핑누락 일치 | 비활성사용 일치 |")
    md_lines.append("|---|---|---|")
    for r in rows_data:
        c = r["correctness"]
        md_lines.append(
            f"| {r['rows']:,} | {'✅' if c['missing_mapping_identical'] else '❌'} | "
            f"{'✅' if c['inactive_usage_identical'] else '❌'} |"
        )

    md_lines.append("\n## 성능 (이 두 검증만, 독립 프로세스 측정)\n")
    md_lines.append("| 행 수 | full: 로드+검사(s) | full RSS(MB) | chunked: 검사(s)* | chunked RSS(MB) | RSS 절감율 |")
    md_lines.append("|---|---|---|---|---|---|")
    for r in rows_data:
        f, c = r["full"], r["chunked"]
        full_total = f["load_seconds"] + f["check_seconds"]
        rss_saving = round((1 - c["memory"]["rss_peak_mb"] / f["memory"]["rss_peak_mb"]) * 100, 1)
        md_lines.append(
            f"| {r['rows']:,} | {round(full_total, 4)} | {f['memory']['rss_peak_mb']} | "
            f"{c['check_seconds']} | {c['memory']['rss_peak_mb']} | {rss_saving}% |"
        )
    md_lines.append(
        "\n\\* chunked는 RAW를 파일에서 바로 스트리밍하므로 별도 '로드' 단계가 없습니다 "
        "(mapping_df만 미리 로드).\n"
    )

    md_content = "\n".join(md_lines) + "\n"

    results_dir = REPO_ROOT / "benchmark" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = results_dir / f"chunk_experiment_{timestamp}.md"
    md_path.write_text(md_content, encoding="utf-8")
    (results_dir / "latest_chunk_experiment.md").write_text(md_content, encoding="utf-8")
    json_path = results_dir / f"chunk_experiment_{timestamp}.json"
    json_path.write_text(json.dumps(rows_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n결과 저장: {md_path}")
    print("\n" + md_content)


if __name__ == "__main__":
    main()
