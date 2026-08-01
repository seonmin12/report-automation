"""
단일 규모(행 수) 벤치마크 실행기 — 항상 독립된 프로세스로 실행된다.

`run_benchmark.py`가 이 스크립트를 매 규모(1만/5만/10만/20만/30만)마다 별도
서브프로세스로 새로 띄워서 호출한다. 한 프로세스 안에서 여러 규모를 연달아
돌리면 `resource.getrusage`의 최대 RSS가 "그 프로세스가 살아있는 동안의 누적
최고치"라서 이전(더 큰) 규모의 메모리 사용량이 다음(더 작은) 규모 측정치에
섞여 들어간다. 그래서 규모마다 완전히 새 프로세스로 격리한다.

이 스크립트는 실패해도 절대 비정상 종료(트레이스백으로 죽는 것)하지 않는다.
각 단계를 개별적으로 try/except로 감싸서, 실패하면 "몇 번째 단계에서 무슨
예외로 실패했는지"를 JSON에 담아 정상 종료(exit code 0)한다. 그래야 부모
프로세스(run_benchmark.py)가 실패 사유를 안전하게 파싱하고 다음 규모로
넘어갈 수 있다.

표준출력의 마지막 줄에 결과 JSON 한 줄만 출력한다 (부모가 파싱하기 쉽게).
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
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime

from src import aggregate, compare, email_writer, image_builder, report_builder, summary_writer, validate


def _max_rss_mb() -> float:
    """resource.ru_maxrss 단위가 플랫폼마다 달라서(macOS=바이트, Linux=KB) MB로 통일."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return raw / (1024 * 1024)
    return raw / 1024


class Timer:
    """with 블록의 소요 시간을 재서 결과 dict에 저장하는 헬퍼."""

    def __init__(self, results: dict, key: str):
        self.results = results
        self.key = key

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.results[self.key] = round(time.perf_counter() - self._start, 4)
        return False  # 예외는 삼키지 않고 그대로 전파 (호출부에서 try/except로 처리)


def run_trial(data_dir: Path, as_of_str: str) -> dict:
    result = {
        "data_dir": str(data_dir),
        "phases": {},        # 4대 분류 합계 (파일로드/merge/검증/리포트생성)
        "sub_phases": {},    # 세부 함수별 시간 (4단계 최적화 비교용)
        "status": "success",
        "failure": None,
    }

    tracemalloc.start()
    completed_phase = None

    try:
        # ------------------------------------------------------------
        # 1. 파일 로드
        # ------------------------------------------------------------
        t0 = time.perf_counter()
        with Timer(result["sub_phases"], "load_portal"):
            portal_df = pd.read_excel(data_dir / "portal_performance.xlsx")
        with Timer(result["sub_phases"], "load_raw"):
            raw_df = pd.read_csv(data_dir / "raw_transactions.csv", encoding="utf-8-sig")
        with Timer(result["sub_phases"], "load_mapping"):
            mapping_df = pd.read_excel(data_dir / "product_mapping.xlsx")
        result["phases"]["파일로드"] = round(time.perf_counter() - t0, 4)
        completed_phase = "파일로드"

        # ------------------------------------------------------------
        # 2. merge (당월 필터링 + 집계 + 포털-RAW 비교)
        # ------------------------------------------------------------
        as_of_date = datetime.strptime(as_of_str, "%Y-%m-%d").date()
        t0 = time.perf_counter()
        with Timer(result["sub_phases"], "filter_current_month"):
            monthly_df = aggregate.filter_current_month(raw_df, as_of_date)
        with Timer(result["sub_phases"], "aggregate_by_operator_product"):
            operator_product_df = aggregate.aggregate_by_operator_product(monthly_df)
        with Timer(result["sub_phases"], "aggregate_by_operator"):
            operator_summary_df = aggregate.aggregate_by_operator(monthly_df)
        with Timer(result["sub_phases"], "compare_portal_vs_raw"):
            compare_df = compare.compare_portal_vs_raw(portal_df, operator_product_df)
        result["phases"]["merge"] = round(time.perf_counter() - t0, 4)
        completed_phase = "merge"

        # ------------------------------------------------------------
        # 3. 검증 (매핑 4종 + 검증상태 부여)
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # 4. 리포트 생성 (xlsx / txt / png / eml) — 임시 디렉터리에만 쓰고 버림
        # ------------------------------------------------------------
        with tempfile.TemporaryDirectory(prefix="mvno_bench_") as tmp:
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

        result["row_counts"] = {
            "raw": len(raw_df),
            "portal": len(portal_df),
            "mapping": len(mapping_df),
            "compare_combos": len(compare_df),
            "error_detail": len(report_builder.build_error_detail_df(compare_df, validation_results)),
        }

    except Exception as exc:  # noqa: BLE001 - 벤치마크 목적상 모든 예외를 잡아서 기록해야 함
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
    parser = argparse.ArgumentParser(description="단일 규모 벤치마크 트라이얼 (내부용, run_benchmark.py가 호출)")
    parser.add_argument("--data-dir", type=str, required=True)
    parser.add_argument("--asof", type=str, required=True)
    args = parser.parse_args()

    result = run_trial(Path(args.data_dir), args.asof)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
