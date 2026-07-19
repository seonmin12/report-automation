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
    """전체 파이프라인 실행."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not (config.PORTAL_FILE.exists() and config.RAW_FILE.exists() and config.MAPPING_FILE.exists()):
        raise FileNotFoundError(
            "포털/RAW/매핑 더미데이터가 없습니다. `python main.py --generate-dummy`로 먼저 생성하세요."
        )

    portal_df = pd.read_excel(config.PORTAL_FILE)
    raw_df = pd.read_csv(config.RAW_FILE, encoding="utf-8-sig")
    mapping_df = pd.read_excel(config.MAPPING_FILE)

    monthly_df = aggregate.filter_current_month(raw_df, as_of_date)
    operator_product_df = aggregate.aggregate_by_operator_product(monthly_df)
    operator_summary_df = aggregate.aggregate_by_operator(monthly_df)

    compare_df = compare.compare_portal_vs_raw(portal_df, operator_product_df)
    validation_results = validate.run_all_validations(raw_df, portal_df, mapping_df)

    date_str = as_of_date.strftime("%Y%m%d")
    xlsx_path = config.OUTPUT_DIR / f"validation_report_{date_str}.xlsx"
    txt_path = config.OUTPUT_DIR / f"summary_{date_str}.txt"
    png_path = config.OUTPUT_DIR / f"summary_{date_str}.png"

    report_builder.build_excel_report(compare_df, validation_results, operator_summary_df, xlsx_path)

    text_summary = summary_writer.build_text_summary(
        as_of_date, compare_df, validation_results, operator_summary_df
    )
    summary_writer.save_text_summary(text_summary, txt_path)

    image_builder.build_summary_image(
        operator_summary_df, png_path, title=f"사업자별 누적가입자 요약 ({date_str})"
    )

    print(text_summary)
    print()
    print(f"엑셀 리포트: {xlsx_path}")
    print(f"텍스트 요약: {txt_path}")
    print(f"요약 이미지: {png_path}")


def main():
    args = parse_args()
    as_of_date = datetime.strptime(args.asof, "%Y-%m-%d").date()

    if args.generate_dummy:
        generate_dummy_data.main()

    run_pipeline(as_of_date)


if __name__ == "__main__":
    main()
