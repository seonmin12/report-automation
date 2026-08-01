"""
4단계: 최적화 전/후 비교 오케스트레이터.

레벨 0(베이스라인) → 1(+dtype) → 2(+usecols) → 3(+merge 키 dtype 정합) 순서로,
5개 규모 전부에 대해 벤치마크 + 정확도 재확인을 실행한다.

각 레벨은 이전 레벨 위에 누적 적용되지만, 비교표에는 "레벨 N vs 레벨 N-1"의
개별 효과가 드러나게 인접 레벨끼리 diff를 계산해서 보여준다 (그래야 "usecols
하나만 얼마나 효과가 있었는지"를 알 수 있음 — 한 번에 다 적용해버리면 안 된다는
지침대로).

정확도는 매 레벨·매 규모마다 ground_truth.json과 재대조한다. 하나라도
불일치가 나오면 그 사실을 결과에 명확히 남긴다 (최적화가 검증 로직의 동작을
바꿔버렸다는 뜻이므로).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DEFAULT_AS_OF_DATE

from benchmark.check_accuracy import compare_against_ground_truth
from benchmark.run_benchmark import DEFAULT_SCALES, ensure_data

REPO_ROOT = Path(__file__).resolve().parent.parent
TRIAL_SCRIPT = Path(__file__).resolve().parent / "_trial_optimized.py"

LEVELS = {
    0: "베이스라인 (dtype/usecols 미지정)",
    1: "+ dtype 지정 (저카디널리티 컬럼 category)",
    2: "+ usecols (안 쓰는 컬럼 제외)",
    3: "+ merge 키 dtype 정합",
}


def run_one(rows: int, data_dir: Path, asof: str, level: int, timeout_sec: int) -> dict:
    wall_start = time.perf_counter()
    try:
        proc = subprocess.run(
            [
                sys.executable, str(TRIAL_SCRIPT),
                "--data-dir", str(data_dir), "--asof", asof, "--level", str(level),
            ],
            capture_output=True, text=True, timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {"rows": rows, "level": level, "status": "failed",
                "failure": {"exception_type": "TimeoutExpired", "exception_message": f"{timeout_sec}초 초과"}}

    if proc.returncode != 0:
        return {
            "rows": rows, "level": level, "status": "failed",
            "failure": {
                "exception_type": "ProcessCrashed",
                "exception_message": f"exit {proc.returncode}: {proc.stderr[-500:] if proc.stderr else ''}",
            },
        }

    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    if not lines:
        return {"rows": rows, "level": level, "status": "failed",
                "failure": {"exception_type": "NoOutput", "exception_message": "결과 JSON 없음"}}

    result = json.loads(lines[-1])
    result["rows"] = rows
    result["wall_seconds"] = round(time.perf_counter() - wall_start, 2)
    return result


def main():
    scales = DEFAULT_SCALES
    seed = 42
    asof = str(DEFAULT_AS_OF_DATE)
    timeout_sec = 600

    all_results = []  # [{rows, level, ...trial result, accuracy}]

    for rows in scales:
        print(f"\n=== {rows:,}행 ===")
        data_dir = ensure_data(rows, seed, asof)
        ground_truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))

        for level in sorted(LEVELS):
            print(f"[{rows:,}행][레벨 {level}] {LEVELS[level]} 실행 중...")
            result = run_one(rows, data_dir, asof, level, timeout_sec)

            if result["status"] == "success":
                validation_summary = result.pop("_validation_summary")
                accuracy = compare_against_ground_truth(validation_summary, ground_truth)
                result["accuracy"] = accuracy
                p = result["phases"]
                m = result["memory"]
                acc_flag = "정확도 OK" if accuracy["passed"] else (
                    f"정확도 불일치! 누락{accuracy['total_missing']}/오탐{accuracy['total_false_positive']}"
                )
                print(
                    f"  총 {p['총합']}s (로드 {p.get('파일로드')}s / merge {p.get('merge')}s / "
                    f"검증 {p.get('검증')}s / 리포트 {p.get('리포트생성')}s), "
                    f"RSS {m['rss_peak_mb']}MB, {acc_flag}"
                )
            else:
                result["accuracy"] = None
                f = result["failure"]
                print(f"  실패: {f['exception_type']}: {f['exception_message']}")

            all_results.append(result)

    # ------------------------------------------------------------
    # 저장
    # ------------------------------------------------------------
    results_dir = REPO_ROOT / "benchmark" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = results_dir / f"optimizations_{timestamp}.json"
    json_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")

    md_content = format_markdown(all_results, scales)
    md_path = results_dir / f"optimizations_{timestamp}.md"
    md_path.write_text(md_content, encoding="utf-8")
    (results_dir / "latest_optimizations.md").write_text(md_content, encoding="utf-8")
    (results_dir / "latest_optimizations.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"\n결과 저장: {md_path}")
    print(f"원본 JSON: {json_path}")


def format_markdown(all_results: list[dict], scales: list[int]) -> str:
    lines = ["# 최적화 전/후 비교 (dtype / usecols / merge 키 정합)\n"]

    lines.append("## 레벨 설명\n")
    for level, desc in LEVELS.items():
        lines.append(f"- **레벨 {level}**: {desc}")
    lines.append("")

    by_rows = {}
    for r in all_results:
        by_rows.setdefault(r["rows"], {})[r["level"]] = r

    lines.append("## 총 소요시간(s) — 레벨별\n")
    header = "| 행 수 | " + " | ".join(f"레벨{l}" for l in sorted(LEVELS)) + " | 레벨0→3 개선율 |"
    lines.append(header)
    lines.append("|---|" + "---|" * (len(LEVELS) + 1))
    for rows in scales:
        row_results = by_rows.get(rows, {})
        cells = []
        for level in sorted(LEVELS):
            r = row_results.get(level)
            if r and r["status"] == "success":
                cells.append(str(r["phases"]["총합"]))
            else:
                cells.append("실패")
        base = row_results.get(0)
        last = row_results.get(3)
        if base and last and base["status"] == "success" and last["status"] == "success":
            base_t, last_t = base["phases"]["총합"], last["phases"]["총합"]
            pct = round((1 - last_t / base_t) * 100, 1) if base_t else 0
            improve = f"{pct}% 단축"
        else:
            improve = "-"
        lines.append(f"| {rows:,} | " + " | ".join(cells) + f" | {improve} |")

    lines.append("\n## RSS 피크 메모리(MB) — 레벨별\n")
    lines.append(header.replace("개선율", "메모리 절감율"))
    lines.append("|---|" + "---|" * (len(LEVELS) + 1))
    for rows in scales:
        row_results = by_rows.get(rows, {})
        cells = []
        for level in sorted(LEVELS):
            r = row_results.get(level)
            if r and r["status"] == "success":
                cells.append(str(r["memory"]["rss_peak_mb"]))
            else:
                cells.append("실패")
        base = row_results.get(0)
        last = row_results.get(3)
        if base and last and base["status"] == "success" and last["status"] == "success":
            base_m, last_m = base["memory"]["rss_peak_mb"], last["memory"]["rss_peak_mb"]
            pct = round((1 - last_m / base_m) * 100, 1) if base_m else 0
            improve = f"{pct}% 절감"
        else:
            improve = "-"
        lines.append(f"| {rows:,} | " + " | ".join(cells) + f" | {improve} |")

    lines.append("\n## 인접 레벨 단독 효과 (각 최적화가 개별적으로 기여한 몫)\n")
    lines.append("| 행 수 | 레벨0→1 (dtype) | 레벨1→2 (usecols) | 레벨2→3 (merge정합) |")
    lines.append("|---|---|---|---|")
    for rows in scales:
        row_results = by_rows.get(rows, {})
        cells = []
        for a, b in ((0, 1), (1, 2), (2, 3)):
            ra, rb = row_results.get(a), row_results.get(b)
            if ra and rb and ra["status"] == "success" and rb["status"] == "success":
                ta, tb = ra["phases"]["총합"], rb["phases"]["총합"]
                delta = round(ta - tb, 4)
                pct = round((1 - tb / ta) * 100, 1) if ta else 0
                cells.append(f"{delta:+.4f}s ({pct:+.1f}%)")
            else:
                cells.append("-")
        lines.append(f"| {rows:,} | " + " | ".join(cells) + " |")

    lines.append("\n## 정확도 재확인 (최적화 전후 탐지 결과가 동일한가)\n")
    lines.append("| 행 수 | 레벨 | 탐지 누락 | 오탐 | 결과 |")
    lines.append("|---|---|---|---|---|")
    any_mismatch = False
    for rows in scales:
        row_results = by_rows.get(rows, {})
        for level in sorted(LEVELS):
            r = row_results.get(level)
            if not r or r["status"] != "success" or r.get("accuracy") is None:
                continue
            acc = r["accuracy"]
            status = "✅" if acc["passed"] else "❌ 불일치"
            if not acc["passed"]:
                any_mismatch = True
            lines.append(f"| {rows:,} | {level} | {acc['total_missing']} | {acc['total_false_positive']} | {status} |")
    if not any_mismatch:
        lines.append("\n(모든 레벨·모든 규모에서 원본과 탐지 결과 완전히 동일 — 누락/오탐 0건)\n")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
