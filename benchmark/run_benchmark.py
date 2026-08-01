"""
벤치마크 하네스.

1만/5만/10만/20만/30만 행 규모로 올려가며 검증 파이프라인 전체(파일로드 → merge →
검증 → 리포트생성)를 실행하고, 단계별 소요시간·피크 메모리(tracemalloc)·최대 RSS를
측정한다.

각 규모는 독립된 서브프로세스(`benchmark/_trial.py`)로 실행한다. 한 프로세스에서
여러 규모를 연달아 돌리면 `resource.getrusage`의 최대 RSS가 프로세스 생존 기간
전체의 누적 최고치라서, 이전 규모의 메모리 사용량이 다음 규모 측정치를 오염시키기
때문이다.

특정 규모가 예외/타임아웃으로 실패해도 잡아서 결과에 "몇 행에서 어떤 예외로
실패했는지" 남기고, 더 큰 규모로 계속 진행한다.

사용 예:
    python benchmark/run_benchmark.py
    python benchmark/run_benchmark.py --scales 10000 50000 --timeout 120
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DEFAULT_AS_OF_DATE

from benchmark import generate_dummy

DEFAULT_SCALES = [10_000, 50_000, 100_000, 200_000, 300_000]
DEFAULT_TIMEOUT_SEC = 600  # 로컬 실행 기준 여유있게. Vercel 실제 한도(300초)와는 별개로 비교용.

REPO_ROOT = Path(__file__).resolve().parent.parent
TRIAL_SCRIPT = Path(__file__).resolve().parent / "_trial.py"


def ensure_data(rows: int, seed: int, asof: str) -> Path:
    """benchmark/data/<rows>/에 더미데이터가 없으면 생성하고, 있으면 재사용."""
    out_dir = REPO_ROOT / "benchmark" / "data" / str(rows)
    required = ["portal_performance.xlsx", "raw_transactions.csv", "product_mapping.xlsx", "ground_truth.json"]
    if out_dir.exists() and all((out_dir / name).exists() for name in required):
        return out_dir

    args = generate_dummy.parse_args(
        ["--rows", str(rows), "--seed", str(seed), "--asof", asof, "--out", str(out_dir)]
    )
    generate_dummy.generate_all(args)
    return out_dir


def run_one_scale(rows: int, data_dir: Path, asof: str, timeout_sec: int) -> dict:
    """서브프로세스로 _trial.py를 실행하고 결과를 파싱. 타임아웃/비정상종료도 실패로 기록."""
    wall_start = time.perf_counter()
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(TRIAL_SCRIPT),
                "--data-dir", str(data_dir),
                "--asof", asof,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {
            "rows": rows,
            "status": "failed",
            "failure": {
                "after_phase": None,
                "exception_type": "TimeoutExpired",
                "exception_message": f"{timeout_sec}초 안에 끝나지 않음 (프로세스 강제 종료)",
                "traceback": None,
            },
            "phases": {},
            "sub_phases": {},
            "memory": None,
            "wall_seconds": round(time.perf_counter() - wall_start, 2),
        }

    wall_seconds = round(time.perf_counter() - wall_start, 2)

    if proc.returncode != 0:
        # _trial.py는 내부 예외를 전부 잡아서 JSON으로 보고하도록 만들어졌으므로,
        # 여기 걸리는 건 OS 강제 종료(OOM killer 등) 같은 진짜 비정상 종료다.
        return {
            "rows": rows,
            "status": "failed",
            "failure": {
                "after_phase": None,
                "exception_type": "ProcessCrashed",
                "exception_message": (
                    f"서브프로세스가 exit code {proc.returncode}로 비정상 종료됨 "
                    "(OOM killer 등에 의한 강제 종료 가능성). stderr 마지막 부분: "
                    + (proc.stderr[-500:] if proc.stderr else "(없음)")
                ),
                "traceback": None,
            },
            "phases": {},
            "sub_phases": {},
            "memory": None,
            "wall_seconds": wall_seconds,
        }

    stdout_lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not stdout_lines:
        return {
            "rows": rows,
            "status": "failed",
            "failure": {
                "after_phase": None,
                "exception_type": "NoOutput",
                "exception_message": "서브프로세스가 결과 JSON을 출력하지 않음",
                "traceback": None,
            },
            "phases": {},
            "sub_phases": {},
            "memory": None,
            "wall_seconds": wall_seconds,
        }

    result = json.loads(stdout_lines[-1])
    result["rows"] = rows
    result["wall_seconds"] = wall_seconds
    return result


def format_markdown(results: list[dict], meta: dict) -> str:
    lines = []
    lines.append("# 벤치마크 결과\n")
    lines.append(f"- 실행 시각: {meta['run_at']}")
    lines.append(f"- 시드: {meta['seed']}")
    lines.append(f"- 기준일: {meta['asof']}")
    lines.append(f"- 타임아웃: {meta['timeout_sec']}초/규모\n")

    lines.append("## 단계별 소요시간 / 피크 메모리\n")
    lines.append("| 행 수 | 파일로드(s) | merge(s) | 검증(s) | 리포트생성(s) | 총합(s) | tracemalloc 피크(MB) | RSS 피크(MB) | 상태 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        rows = f"{r['rows']:,}"
        if r["status"] == "success":
            p = r["phases"]
            m = r["memory"]
            lines.append(
                f"| {rows} | {p.get('파일로드', '-')} | {p.get('merge', '-')} | {p.get('검증', '-')} | "
                f"{p.get('리포트생성', '-')} | {p.get('총합', '-')} | {m['tracemalloc_peak_mb']} | "
                f"{m['rss_peak_mb']} | ✅ 성공 |"
            )
        else:
            f = r["failure"]
            lines.append(
                f"| {rows} | - | - | - | - | - | - | - | "
                f"❌ 실패 ({f.get('after_phase') or '시작 전'} 단계 이후, {f['exception_type']}) |"
            )

    lines.append("\n## 실패 상세\n")
    any_failure = False
    for r in results:
        if r["status"] != "success":
            any_failure = True
            f = r["failure"]
            lines.append(f"### {r['rows']:,}행")
            lines.append(f"- 실패 시점: {f.get('after_phase') or '시작 전 (파일로드 이전)'} 단계 완료 직후")
            lines.append(f"- 예외 유형: `{f['exception_type']}`")
            lines.append(f"- 메시지: {f['exception_message']}")
            lines.append("")
    if not any_failure:
        lines.append("(실패한 규모 없음)\n")

    lines.append("## 세부 함수별 소요시간 (4단계 최적화 비교용)\n")
    header = "| 행 수 | " + " | ".join(sorted({k for r in results if r["status"] == "success" for k in r["sub_phases"]})) + " |"
    sub_keys = sorted({k for r in results if r["status"] == "success" for k in r["sub_phases"]})
    lines.append("| 행 수 | " + " | ".join(sub_keys) + " |")
    lines.append("|---|" + "---|" * len(sub_keys))
    for r in results:
        if r["status"] != "success":
            continue
        row = [f"{r['rows']:,}"] + [str(r["sub_phases"].get(k, "-")) for k in sub_keys]
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="벤치마크 하네스: 여러 규모로 파이프라인 실행 및 측정")
    parser.add_argument("--scales", type=int, nargs="+", default=DEFAULT_SCALES, help="테스트할 행 수 목록")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--asof", type=str, default=str(DEFAULT_AS_OF_DATE))
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC, help="규모당 타임아웃(초)")
    args = parser.parse_args()

    results = []
    for rows in args.scales:
        print(f"[{rows:,}행] 데이터 준비 중...")
        data_dir = ensure_data(rows, args.seed, args.asof)

        print(f"[{rows:,}행] 벤치마크 실행 중 (타임아웃 {args.timeout}초)...")
        result = run_one_scale(rows, data_dir, args.asof, args.timeout)
        results.append(result)

        if result["status"] == "success":
            p = result["phases"]
            m = result["memory"]
            print(
                f"[{rows:,}행] 성공 — 총 {p['총합']}s "
                f"(로드 {p.get('파일로드')}s / merge {p.get('merge')}s / 검증 {p.get('검증')}s / "
                f"리포트 {p.get('리포트생성')}s), RSS 피크 {m['rss_peak_mb']}MB"
            )
        else:
            f = result["failure"]
            print(f"[{rows:,}행] 실패 — {f['after_phase'] or '시작 전'} 단계 이후 {f['exception_type']}: {f['exception_message']}")

    results_dir = REPO_ROOT / "benchmark" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    meta = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "asof": args.asof,
        "timeout_sec": args.timeout,
        "scales": args.scales,
    }

    json_path = results_dir / f"benchmark_{timestamp}.json"
    json_path.write_text(
        json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md_path = results_dir / f"benchmark_{timestamp}.md"
    md_content = format_markdown(results, meta)
    md_path.write_text(md_content, encoding="utf-8")

    latest_md = results_dir / "latest.md"
    latest_json = results_dir / "latest.json"
    latest_md.write_text(md_content, encoding="utf-8")
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"\n결과 저장: {md_path}")
    print(f"원본 JSON: {json_path}")
    print("\n" + md_content)


if __name__ == "__main__":
    main()
