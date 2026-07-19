"""
전체 파이프라인 실행 진입점 (CLI).

실행 예:
    python main.py --asof 2026-07-19
    python main.py --generate-dummy   # 더미데이터부터 새로 생성하고 싶을 때
"""

import argparse
from datetime import date, datetime

import pandas as pd

import config
from src import (
    generate_dummy_data,
    aggregate,
    compare,
    validate,
    report_builder,
    summary_writer,
    image_builder,
)


def parse_args():
    parser = argparse.ArgumentParser(description="실적 데이터 검증 및 리포트 자동화")
    parser.add_argument(
        "--asof",
        type=str,
        default=str(config.DEFAULT_AS_OF_DATE),
        help="집계 기준일 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--generate-dummy",
        action="store_true",
        help="더미데이터를 새로 생성한 뒤 파이프라인 실행",
    )
    return parser.parse_args()


def run_pipeline(as_of_date: date):
    """전체 파이프라인 실행.

    TODO 순서:
    1. data/ 에서 포털/RAW/매핑 파일 로드 (pd.read_excel / pd.read_csv)
    2. aggregate.filter_current_month + aggregate_by_operator_product / aggregate_by_operator
    3. compare.compare_portal_vs_raw
    4. validate.run_all_validations
    5. report_builder.build_excel_report → output/validation_report_YYYYMMDD.xlsx
    6. summary_writer.build_text_summary + save_text_summary → output/summary_YYYYMMDD.txt
    7. image_builder.build_summary_image → output/summary_YYYYMMDD.png
    """
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raise NotImplementedError("파이프라인 구현 예정")


def main():
    args = parse_args()
    as_of_date = datetime.strptime(args.asof, "%Y-%m-%d").date()

    if args.generate_dummy:
        generate_dummy_data.main()

    run_pipeline(as_of_date)


if __name__ == "__main__":
    main()
