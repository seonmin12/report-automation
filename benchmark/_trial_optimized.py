"""
`_trial.py`와 동일한 구조의 단일 규모 벤치마크 실행기이지만, `optimized.py`의
레벨별 로딩/merge 방식을 쓴다. 독립 프로세스로 실행하는 이유도 `_trial.py`와
동일 (RSS 피크 오염 방지).

레벨 0 결과는 `_trial.py`의 결과와 (같은 데이터·같은 코드 경로이므로) 사실상
동일해야 한다 — 이건 이 스크립트 자체의 자기 검증이기도 하다.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import tempfile
import time
import tracemalloc
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import aggregate, email_writer, image_builder, report_builder, summary_writer, validate

from benchmark import optimized


def _max_rss_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return raw / (1024 * 1024)
    return raw / 1024


class Timer:
    def __init__(self, results: dict, key: str):
        self.results = results
        self.key = key

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.results[self.key] = round(time.perf_counter() - self._start, 4)
        return False


def run_trial(data_dir: Path, as_of_str: str, level: int) -> dict:
    result = {
        "data_dir": str(data_dir),
        "level": level,
        "phases": {},
        "sub_phases": {},
        "status": "success",
        "failure": None,
    }

    tracemalloc.start()
    completed_phase = None

    try:
        t0 = time.perf_counter()
        with Timer(result["sub_phases"], "load_files"):
            portal_df, raw_df, mapping_df = optimized.load_files(data_dir, level)
        result["phases"]["파일로드"] = round(time.perf_counter() - t0, 4)
        completed_phase = "파일로드"

        as_of_date = datetime.strptime(as_of_str, "%Y-%m-%d").date()
        t0 = time.perf_counter()
        with Timer(result["sub_phases"], "filter_current_month"):
            monthly_df = aggregate.filter_current_month(raw_df, as_of_date)
        with Timer(result["sub_phases"], "aggregate_by_operator_product"):
            operator_product_df = aggregate.aggregate_by_operator_product(monthly_df)
        with Timer(result["sub_phases"], "aggregate_by_operator"):
            operator_summary_df = aggregate.aggregate_by_operator(monthly_df)
        with Timer(result["sub_phases"], "compare_portal_vs_raw"):
            compare_df = optimized.compare_portal_vs_raw(
                portal_df, operator_product_df, align_merge_dtype=(level >= 3)
            )
        result["phases"]["merge"] = round(time.perf_counter() - t0, 4)
        completed_phase = "merge"

        t0 = time.perf_counter()
        with Timer(result["sub_phases"], "check_missing_mapping"):
            missing = validate.check_missing_mapping(raw_df, mapping_df)
        with Timer(result["sub_phases"], "check_duplicate_mapping"):
            duplicate = validate.check_duplicate_mapping(mapping_df)
        with Timer(result["sub_phases"], "check_inactive_product_usage"):
            inactive = validate.check_inactive_product_usage(raw_df, mapping_df)
        with Timer(result["sub_phases"], "check_name_mismatch"):
            mismatch = validate.check_name_mismatch(raw_df, portal_df, mapping_df)
        validation_results = {
            validate.ISSUE_KEY_MISSING_MAPPING: missing,
            validate.ISSUE_KEY_DUPLICATE_MAPPING: duplicate,
            validate.ISSUE_KEY_INACTIVE_USAGE: inactive,
            validate.ISSUE_KEY_NAME_MISMATCH: mismatch,
        }
        with Timer(result["sub_phases"], "attach_validation_status"):
            operator_summary_df = aggregate.attach_validation_status(
                operator_summary_df, compare_df, validation_results
            )
        result["phases"]["검증"] = round(time.perf_counter() - t0, 4)
        completed_phase = "검증"

        with tempfile.TemporaryDirectory(prefix="mvno_bench_opt_") as tmp:
            tmp_dir = Path(tmp)
            t0 = time.perf_counter()
            with Timer(result["sub_phases"], "build_excel_report"):
                report_builder.build_excel_report(
                    as_of_date, compare_df, validation_results, operator_summary_df,
                    tmp_dir / "validation_report.xlsx",
                )
            with Timer(result["sub_phases"], "build_text_summary"):
                text_summary = summary_writer.build_text_summary(
                    as_of_date, compare_df, validation_results, operator_summary_df
                )
            with Timer(result["sub_phases"], "build_summary_image"):
                image_builder.build_summary_image(operator_summary_df, tmp_dir / "summary.png")
            with Timer(result["sub_phases"], "build_email_draft"):
                email_writer.build_email_draft(
                    as_of_date, text_summary, attachment_paths=[tmp_dir / "validation_report.xlsx"]
                )
            result["phases"]["리포트생성"] = round(time.perf_counter() - t0, 4)
        completed_phase = "리포트생성"

        # 정확도 재확인용으로 결과 자체도 반환 (부모 프로세스가 ground_truth와 대조)
        result["_validation_summary"] = {
            "매핑누락": sorted(missing["상품코드"].astype(str).tolist()),
            "중복": sorted(duplicate["상품코드"].astype(str).tolist()),
            "비활성사용": sorted(inactive["상품코드"].astype(str).tolist()),
            "명칭불일치": sorted(mismatch["상품코드"].astype(str).tolist()),
            "실적비교": [
                {"사업자코드": str(o), "상품코드": str(p)}
                for o, p in zip(
                    compare_df.loc[compare_df[optimized.compare_module.COL_ISSUE_FLAG], "사업자코드"],
                    compare_df.loc[compare_df[optimized.compare_module.COL_ISSUE_FLAG], "상품코드"],
                )
            ],
        }

    except Exception as exc:  # noqa: BLE001
        result["status"] = "failed"
        result["failure"] = {
            "after_phase": completed_phase,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc(),
        }

    finally:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result["memory"] = {
            "tracemalloc_peak_mb": round(peak / (1024 * 1024), 2),
            "rss_peak_mb": round(_max_rss_mb(), 2),
        }
        result["phases"]["총합"] = round(sum(v for k, v in result["phases"].items() if k != "총합"), 4)

    return result


def main():
    parser = argparse.ArgumentParser(description="레벨별 최적화 벤치마크 트라이얼 (내부용)")
    parser.add_argument("--data-dir", type=str, required=True)
    parser.add_argument("--asof", type=str, required=True)
    parser.add_argument("--level", type=int, required=True, choices=[0, 1, 2, 3])
    args = parser.parse_args()

    result = run_trial(Path(args.data_dir), args.asof, args.level)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
