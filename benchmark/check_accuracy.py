"""
검증 정확도 측정 스크립트.

1단계(`generate_dummy.py`)가 주입하고 `ground_truth.json`에 남긴 "정답"과, 실제
`validate.py`/`compare.py`가 탐지한 결과를 대조한다.

accuracy(정확도) 지표는 일부러 안 쓴다 — 정상 데이터가 압도적으로 많은 상황에서는
"그냥 다 정상이라고 찍어도" accuracy가 99%+ 나오는, 의미 없는 지표이기 때문이다.
대신 아래 두 개를 절대 건수로 본다.

- 탐지 누락(false negative): 주입했는데 못 잡은 것 — 실무에서는 "오류인데 통과시킴"
- 오탐(false positive): 안 넣었는데 오류로 잡은 것 — 실무에서는 "정상인데 확인필요로 잘못 표시" (더 중요)

4단계(최적화)에서 코드가 바뀔 때마다 이 스크립트를 다시 돌려서, 최적화 전후로
탐지 결과가 완전히 같은지(누락 0, 오탐 0을 그대로 유지하는지) 확인하는 용도로 쓴다.

사용 예:
    python benchmark/check_accuracy.py                    # benchmark/data/ 아래 모든 규모
    python benchmark/check_accuracy.py --scales 10000      # 특정 규모만
    python benchmark/check_accuracy.py --data-dir benchmark/data/10000  # 디렉터리 직접 지정
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import COL_OPERATOR_CODE, COL_PRODUCT_CODE
from src import aggregate, compare, validate

REPO_ROOT = Path(__file__).resolve().parent.parent

MAPPING_ISSUE_TYPES = {
    "매핑누락": validate.ISSUE_KEY_MISSING_MAPPING,
    "중복": validate.ISSUE_KEY_DUPLICATE_MAPPING,
    "비활성사용": validate.ISSUE_KEY_INACTIVE_USAGE,
    "명칭불일치": validate.ISSUE_KEY_NAME_MISMATCH,
}


def _combo_set(records: list[dict]) -> set[tuple]:
    return {(r[COL_OPERATOR_CODE], r[COL_PRODUCT_CODE]) for r in records}


def compare_against_ground_truth(validation_summary: dict, ground_truth: dict) -> dict:
    """탐지 결과 요약(dict of 상품코드/조합 리스트) vs 정답을 대조.

    validation_summary 형식: {
        "매핑누락": [상품코드, ...], "중복": [...], "비활성사용": [...], "명칭불일치": [...],
        "실적비교": [{"사업자코드": ..., "상품코드": ...}, ...],
    }
    원본 경로(check_accuracy_for_dir)와 최적화 실험 경로(run_optimizations.py) 둘 다
    이 함수 하나로 대조한다 — 대조 로직이 두 곳에서 어긋나면 그 자체가 버그이므로,
    아예 한 곳에만 존재하게 만들었다.
    """
    breakdown = {}
    total_missing = 0
    total_false_positive = 0

    for label in MAPPING_ISSUE_TYPES:
        expected = set(ground_truth[label])
        detected = set(validation_summary[label])
        missing = sorted(expected - detected)
        false_positive = sorted(detected - expected)
        breakdown[label] = {
            "expected_count": len(expected),
            "detected_count": len(detected),
            "missing_count": len(missing),
            "false_positive_count": len(false_positive),
            "missing": missing,
            "false_positive": false_positive,
        }
        total_missing += len(missing)
        total_false_positive += len(false_positive)

    expected_compare = set()
    for sub_key in ("perturbed", "raw_only", "portal_only"):
        expected_compare |= _combo_set(ground_truth["실적비교"][sub_key])
    detected_compare = _combo_set(validation_summary["실적비교"])

    missing_compare = sorted(expected_compare - detected_compare)
    false_positive_compare = sorted(detected_compare - expected_compare)
    breakdown["실적비교"] = {
        "expected_count": len(expected_compare),
        "detected_count": len(detected_compare),
        "missing_count": len(missing_compare),
        "false_positive_count": len(false_positive_compare),
        "missing": [{"사업자코드": o, "상품코드": p} for o, p in missing_compare],
        "false_positive": [{"사업자코드": o, "상품코드": p} for o, p in false_positive_compare],
    }
    total_missing += len(missing_compare)
    total_false_positive += len(false_positive_compare)

    return {
        "breakdown": breakdown,
        "total_missing": total_missing,
        "total_false_positive": total_false_positive,
        "passed": total_missing == 0 and total_false_positive == 0,
    }


def check_accuracy_for_dir(data_dir: Path) -> dict:
    """한 규모(디렉터리)에 대해 정답 vs 실제 탐지를 대조 (원본 코드 경로, dtype/usecols 미지정)."""
    portal_df = pd.read_excel(data_dir / "portal_performance.xlsx")
    raw_df = pd.read_csv(data_dir / "raw_transactions.csv", encoding="utf-8-sig")
    mapping_df = pd.read_excel(data_dir / "product_mapping.xlsx")
    ground_truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))

    validation_results = validate.run_all_validations(raw_df, portal_df, mapping_df)

    as_of_date = datetime.strptime(ground_truth["meta"]["as_of_date"], "%Y-%m-%d").date()
    monthly_df = aggregate.filter_current_month(raw_df, as_of_date)
    raw_agg_df = aggregate.aggregate_by_operator_product(monthly_df)
    compare_df = compare.compare_portal_vs_raw(portal_df, raw_agg_df)

    issue_rows = compare_df[compare_df[compare.COL_ISSUE_FLAG]]
    validation_summary = {
        "매핑누락": validation_results[validate.ISSUE_KEY_MISSING_MAPPING][COL_PRODUCT_CODE].tolist(),
        "중복": validation_results[validate.ISSUE_KEY_DUPLICATE_MAPPING][COL_PRODUCT_CODE].tolist(),
        "비활성사용": validation_results[validate.ISSUE_KEY_INACTIVE_USAGE][COL_PRODUCT_CODE].tolist(),
        "명칭불일치": validation_results[validate.ISSUE_KEY_NAME_MISMATCH][COL_PRODUCT_CODE].tolist(),
        "실적비교": [
            {"사업자코드": o, "상품코드": p}
            for o, p in zip(issue_rows[COL_OPERATOR_CODE], issue_rows[COL_PRODUCT_CODE])
        ],
    }

    outcome = compare_against_ground_truth(validation_summary, ground_truth)
    return {
        "data_dir": str(data_dir),
        "rows": ground_truth["meta"]["rows"],
        **outcome,
    }


def format_markdown(results: list[dict]) -> str:
    lines = []
    lines.append("# 검증 정확도 측정 결과\n")
    lines.append(
        "accuracy(정확도) 지표는 쓰지 않습니다 — 정상 데이터가 압도적으로 많아 의미가 없어서,\n"
        "**탐지 누락 건수**와 **오탐 건수**를 절대 수치로 봅니다.\n"
    )

    lines.append("## 요약\n")
    lines.append("| 행 수 | 탐지 누락 | 오탐 | 결과 |")
    lines.append("|---|---|---|---|")
    for r in results:
        status = "✅ 누락/오탐 0건" if r["passed"] else "❌ 불일치 있음"
        lines.append(f"| {r['rows']:,} | {r['total_missing']} | {r['total_false_positive']} | {status} |")

    lines.append("\n## 오류 유형별 분해\n")
    lines.append("| 행 수 | 오류 유형 | 정답 건수 | 탐지 건수 | 누락 | 오탐 |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        for label, b in r["breakdown"].items():
            lines.append(
                f"| {r['rows']:,} | {label} | {b['expected_count']} | {b['detected_count']} | "
                f"{b['missing_count']} | {b['false_positive_count']} |"
            )

    any_mismatch = any(not r["passed"] for r in results)
    if any_mismatch:
        lines.append("\n## 불일치 상세\n")
        for r in results:
            if r["passed"]:
                continue
            lines.append(f"### {r['rows']:,}행\n")
            for label, b in r["breakdown"].items():
                if b["missing_count"] == 0 and b["false_positive_count"] == 0:
                    continue
                lines.append(f"**{label}**")
                if b["missing"]:
                    lines.append(f"- 누락: {b['missing']}")
                if b["false_positive"]:
                    lines.append(f"- 오탐: {b['false_positive']}")
                lines.append("")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="검증 정확도 측정 (정답 vs 실제 탐지 대조)")
    parser.add_argument("--data-dir", type=str, default=None, help="특정 디렉터리 하나만 검사")
    parser.add_argument(
        "--scales", type=int, nargs="+", default=None, help="benchmark/data/<rows>/ 중 검사할 규모 목록 (기본: 존재하는 전부)"
    )
    args = parser.parse_args()

    data_dirs: list[Path]
    if args.data_dir:
        data_dirs = [Path(args.data_dir)]
    else:
        base = REPO_ROOT / "benchmark" / "data"
        if args.scales:
            data_dirs = [base / str(rows) for rows in args.scales]
        else:
            data_dirs = sorted(
                (p for p in base.iterdir() if p.is_dir() and (p / "ground_truth.json").exists()),
                key=lambda p: int(p.name) if p.name.isdigit() else p.name,
            )

    if not data_dirs:
        print("검사할 데이터가 없습니다. 먼저 generate_dummy.py 또는 run_benchmark.py를 실행하세요.")
        return

    results = []
    for data_dir in data_dirs:
        if not (data_dir / "ground_truth.json").exists():
            print(f"[건너뜀] {data_dir}: ground_truth.json 없음")
            continue
        print(f"[{data_dir.name}] 검사 중...")
        result = check_accuracy_for_dir(data_dir)
        results.append(result)
        status = "통과 (누락 0, 오탐 0)" if result["passed"] else (
            f"불일치 — 누락 {result['total_missing']}건, 오탐 {result['total_false_positive']}건"
        )
        print(f"[{data_dir.name}] {status}")

    results_dir = REPO_ROOT / "benchmark" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = results_dir / f"accuracy_{timestamp}.json"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    md_content = format_markdown(results)
    md_path = results_dir / f"accuracy_{timestamp}.md"
    md_path.write_text(md_content, encoding="utf-8")

    (results_dir / "latest_accuracy.md").write_text(md_content, encoding="utf-8")
    (results_dir / "latest_accuracy.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"\n결과 저장: {md_path}")
    print(f"원본 JSON: {json_path}")
    print("\n" + md_content)


if __name__ == "__main__":
    main()
