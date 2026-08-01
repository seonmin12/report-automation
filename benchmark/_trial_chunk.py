"""
청크 처리 실험의 단일 트라이얼 (독립 프로세스로 실행, RSS 오염 방지 동일 이유).

--mode full: raw_df 전체를 한 번에 읽어서 원본 validate.py 함수 그대로 호출.
--mode chunked: raw_df를 파일에서 청크로 스트리밍하며 chunked_check.py로 계산.

둘 다 "매핑누락 + 비활성사용" 두 검증만 수행한다 (이 실험의 범위 그대로).
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
import tracemalloc
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import validate

from benchmark import chunked_check


def _max_rss_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return raw / (1024 * 1024)
    return raw / 1024


def run_full(data_dir: Path) -> dict:
    t0 = time.perf_counter()
    mapping_df = pd.read_excel(data_dir / "product_mapping.xlsx")
    raw_df = pd.read_csv(data_dir / "raw_transactions.csv", encoding="utf-8-sig")
    load_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    missing = validate.check_missing_mapping(raw_df, mapping_df)
    inactive = validate.check_inactive_product_usage(raw_df, mapping_df)
    check_time = time.perf_counter() - t0

    return {
        "load_seconds": round(load_time, 4),
        "check_seconds": round(check_time, 4),
        "missing_codes": sorted(missing["상품코드"].astype(str).tolist()),
        "inactive_codes": sorted(inactive["상품코드"].astype(str).tolist()),
    }


def run_chunked(data_dir: Path, chunksize: int) -> dict:
    t0 = time.perf_counter()
    mapping_df = pd.read_excel(data_dir / "product_mapping.xlsx")
    load_time = time.perf_counter() - t0  # RAW는 여기서 안 읽는다 (체크 단계에서 스트리밍)

    t0 = time.perf_counter()
    missing = chunked_check.check_missing_mapping_chunked(
        data_dir / "raw_transactions.csv", mapping_df, chunksize
    )
    inactive = chunked_check.check_inactive_product_usage_chunked(
        data_dir / "raw_transactions.csv", mapping_df, chunksize
    )
    check_time = time.perf_counter() - t0

    return {
        "load_seconds": round(load_time, 4),
        "check_seconds": round(check_time, 4),
        "missing_codes": sorted(missing["상품코드"].astype(str).tolist()),
        "inactive_codes": sorted(inactive["상품코드"].astype(str).tolist()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, required=True)
    parser.add_argument("--mode", choices=["full", "chunked"], required=True)
    parser.add_argument("--chunksize", type=int, default=20_000)
    args = parser.parse_args()

    tracemalloc.start()
    try:
        if args.mode == "full":
            result = run_full(Path(args.data_dir))
        else:
            result = run_chunked(Path(args.data_dir), args.chunksize)
        result["status"] = "success"
    except Exception as exc:  # noqa: BLE001
        result = {"status": "failed", "exception_type": type(exc).__name__, "exception_message": str(exc)}
    finally:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    result["mode"] = args.mode
    result["memory"] = {
        "tracemalloc_peak_mb": round(peak / (1024 * 1024), 2),
        "rss_peak_mb": round(_max_rss_mb(), 2),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
