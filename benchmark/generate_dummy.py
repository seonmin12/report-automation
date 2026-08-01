"""
벤치마크용 대규모 더미데이터 생성기.

`src/generate_dummy_data.py`(고정 5,000행짜리 데모용)와 달리, 행 수를 인자로 받아
1천~수십만 행 규모로 임의로 만들 수 있다. 100% 합성 데이터이며 실제 사내 데이터
파일은 전혀 읽지 않는다. `config.py`에서 가져오는 값도 컬럼명 상수와, 이미
가상으로 확정된 사업자 8곳/요금제 유형 5종 같은 기존 더미 스키마뿐이다.

핵심 설계 원칙
--------------
1. 카디널리티 통제: 사업자코드(8개 고정), 요금제유형/선후불구분/채널(고정 소수)처럼
   실제로도 고유값이 적은 컬럼은 --rows가 커져도 고유값 개수가 거의 늘지 않는다.
   상품 수만 sqrt 비례로 완만히 늘어난다 (rows=5,000일 때 60개인 원본 비율을 그대로
   유지하면서, rows=300,000이어도 수백 개 수준에 머물도록).
2. 오류는 확률이 아니라 개수로 주입한다: "정해진 개수만큼" 넣어야 하므로, 각 오류
   유형에 해당하는 상품코드/조합을 먼저 정확히 고르고, 그 코드가 RAW에 최소 1회
   이상 반드시 등장하도록 강제 배정한다. 순수 확률 기반이면 --rows가 작을 때
   드문 코드가 우연히 한 번도 안 뽑혀서 정답과 실제 결과가 어긋날 수 있다.
3. 정답 목록(ground_truth.json)은 검증 로직이 실제로 리포트하는 단위(상품코드,
   또는 사업자코드+상품코드 조합)로 저장한다. 3단계 정확도 측정 스크립트가
   이 파일과 validate.py/compare.py의 실제 출력을 바로 대조할 수 있게 하기 위함이다.

사용 예:
    python benchmark/generate_dummy.py --rows 10000 --seed 42
    python benchmark/generate_dummy.py --rows 300000 --out benchmark/data/300000
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

# 저장소 루트(config.py가 있는 위치)를 sys.path에 추가한다. 이렇게 해야
# `python benchmark/generate_dummy.py`처럼 스크립트를 직접 실행해도(= cwd나
# 실행 방식과 무관하게) config 모듈을 찾을 수 있다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    COL_CHANNEL,
    COL_MAPPING_DATE,
    COL_NET_COUNT,
    COL_NEW_COUNT,
    COL_CHURN_COUNT,
    COL_NOTE,
    COL_OPERATOR_CODE,
    COL_OPERATOR_NAME,
    COL_PAYMENT_TYPE,
    COL_PLAN_TYPE,
    COL_PRODUCT_CODE,
    COL_PRODUCT_NAME,
    COL_REGISTERED_AT,
    COL_TXN_DATE,
    COL_TXN_ID,
    COL_TXN_TYPE,
    COL_USE_YN,
    CHANNELS,
    DEFAULT_AS_OF_DATE,
    DUMMY_OPERATORS,
    PAYMENT_TYPES,
    PLAN_TYPES,
    TXN_TYPE_CHURN,
    TXN_TYPE_NEW,
    USE_YN_ACTIVE,
    USE_YN_INACTIVE,
)

# ------------------------------------------------------------------
# 기본 오류 주입 비율 (src/generate_dummy_data.py와 동일한 비율을 그대로 사용해
# rows=5,000 부근에서는 기존 더미데이터와 비슷한 밀도가 되도록 맞췄다)
# ------------------------------------------------------------------
_BASELINE_ROWS = 5000
_BASELINE_PRODUCTS = 60

DEFAULT_UNMAPPED_TXN_RATIO = 0.03
DEFAULT_INACTIVE_TXN_RATIO = 0.02
PREV_MONTH_TXN_RATIO = 0.15
NEW_TXN_RATIO = 0.7


def _default_n_products(rows: int) -> int:
    """상품 수는 행 수에 선형 비례하지 않고 sqrt 비례로 완만히 늘린다.

    실제 MVNO 상품 카탈로그는 거래량이 늘어난다고 그만큼 늘어나지 않는,
    전형적인 저카디언리티 컬럼이기 때문이다. rows=5,000일 때 60개(기존
    더미데이터와 동일)가 되도록 계수를 맞췄다.
    """
    return max(_BASELINE_PRODUCTS, round(_BASELINE_PRODUCTS * (rows / _BASELINE_ROWS) ** 0.5))


def _default_count(rows: int, per_rows: int, minimum: int) -> int:
    """오류 주입 개수 기본값: rows가 커질수록 완만히 늘리되 최소값은 보장."""
    return max(minimum, rows // per_rows)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="벤치마크용 대규모 더미데이터 생성")
    parser.add_argument("--rows", type=int, default=10_000, help="RAW 거래 행 수")
    parser.add_argument("--seed", type=int, default=42, help="난수 시드 (재현성)")
    parser.add_argument(
        "--asof", type=str, default=str(DEFAULT_AS_OF_DATE), help="집계 기준일 (YYYY-MM-DD)"
    )
    parser.add_argument("--out", type=str, default=None, help="출력 디렉터리 (기본: benchmark/data/<rows>)")
    parser.add_argument("--products", type=int, default=None, help="매핑 기준표 상품 수 (기본: rows 기반 자동 산정)")

    parser.add_argument("--n-unmapped", type=int, default=None, help="매핑 누락 상품코드 개수")
    parser.add_argument("--n-duplicate", type=int, default=None, help="중복 매핑 상품코드 개수")
    parser.add_argument("--n-inactive", type=int, default=None, help="비활성 상품 사용 상품코드 개수")
    parser.add_argument("--n-mismatch", type=int, default=None, help="상품명 불일치 상품코드 개수")
    parser.add_argument(
        "--n-compare-perturb", type=int, default=None, help="포털 실적값을 임계치 이상 어긋나게 할 사업자-상품 조합 개수"
    )
    parser.add_argument(
        "--n-portal-only", type=int, default=None, help="포털에만 존재(RAW 없음)하는 사업자-상품 조합 개수"
    )
    parser.add_argument(
        "--n-raw-only", type=int, default=None, help="RAW에만 존재(포털 누락)하는 사업자-상품 조합 개수"
    )
    return parser.parse_args(argv)


def generate_mapping(
    rng: random.Random,
    n_products: int,
    n_duplicate: int,
    n_inactive: int,
    as_of_date: date,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """매핑 기준표 생성.

    Returns:
        (mapping_df, duplicated_codes, inactive_codes)
        - duplicated_codes: 중복 등록된 상품코드 목록 (정답)
        - inactive_codes: 비활성 처리된 상품코드 목록 (정답 후보. 실제 RAW에서
          쓰여야 최종 정답이 되므로, generate_raw에서 사용 여부를 확정한다)
    """
    operators = DUMMY_OPERATORS
    rows = []
    for i in range(1, n_products + 1):
        operator = operators[i % len(operators)]
        plan_type = PLAN_TYPES[i % len(PLAN_TYPES)]
        registered_at = as_of_date - timedelta(days=rng.randint(30, 365))
        rows.append(
            {
                COL_PRODUCT_CODE: f"PRD{i:06d}",
                COL_PRODUCT_NAME: f"{plan_type} {i:06d}",
                COL_PLAN_TYPE: plan_type,
                COL_OPERATOR_CODE: operator[COL_OPERATOR_CODE],
                COL_USE_YN: USE_YN_ACTIVE,
                COL_MAPPING_DATE: registered_at,
                COL_NOTE: "",
            }
        )
    mapping_df = pd.DataFrame(rows)

    all_idx = list(mapping_df.index)
    inactive_idx = rng.sample(all_idx, n_inactive)
    mapping_df.loc[inactive_idx, COL_USE_YN] = USE_YN_INACTIVE
    mapping_df.loc[inactive_idx, COL_NOTE] = "서비스 종료 상품"
    inactive_codes = mapping_df.loc[inactive_idx, COL_PRODUCT_CODE].tolist()

    remaining_idx = [idx for idx in all_idx if idx not in inactive_idx]
    dup_source_idx = rng.sample(remaining_idx, n_duplicate)
    dup_rows = mapping_df.loc[dup_source_idx].copy()
    dup_rows[COL_NOTE] = "중복 등록"
    duplicated_codes = mapping_df.loc[dup_source_idx, COL_PRODUCT_CODE].tolist()

    mapping_df = pd.concat([mapping_df, dup_rows], ignore_index=True)
    mapping_df = mapping_df.sort_values(COL_PRODUCT_CODE).reset_index(drop=True)
    return mapping_df, duplicated_codes, inactive_codes


def _forced_batches(codes: list[str], total_rows: int) -> dict[str, int]:
    """각 코드에 최소 1행씩 돌아가도록 total_rows를 코드별로 나눈다."""
    if not codes:
        return {}
    total_rows = max(total_rows, len(codes))
    base, extra = divmod(total_rows, len(codes))
    return {code: base + (1 if idx < extra else 0) for idx, code in enumerate(codes)}


def generate_raw(
    rng: random.Random,
    mapping_df: pd.DataFrame,
    n_rows: int,
    n_unmapped: int,
    inactive_codes: list[str],
    n_mismatch: int,
    as_of_date: date,
) -> tuple[pd.DataFrame, list[str], list[str], dict[str, str]]:
    """RAW 거래 데이터 생성.

    Returns:
        (raw_df, unmapped_codes, mismatch_codes, unmapped_code_operator)
    """
    unique_mapping = mapping_df.drop_duplicates(COL_PRODUCT_CODE).set_index(COL_PRODUCT_CODE)
    active_codes = unique_mapping.index[unique_mapping[COL_USE_YN] == USE_YN_ACTIVE].tolist()
    code_to_name = unique_mapping[COL_PRODUCT_NAME]
    code_to_operator = unique_mapping[COL_OPERATOR_CODE]
    operator_codes = [op[COL_OPERATOR_CODE] for op in DUMMY_OPERATORS]

    unmapped_codes = [f"PRDX{i:05d}" for i in range(1, n_unmapped + 1)]
    unmapped_code_operator = {code: rng.choice(operator_codes) for code in unmapped_codes}

    mismatch_codes = rng.sample(active_codes, min(n_mismatch, len(active_codes)))

    # 오류 주입용 강제 배정 행 수 (전체 행 수의 정해진 비율만큼을, 코드별로 최소 1행 보장하며 분배)
    unmapped_total = max(len(unmapped_codes), round(n_rows * DEFAULT_UNMAPPED_TXN_RATIO))
    inactive_total = max(len(inactive_codes), round(n_rows * DEFAULT_INACTIVE_TXN_RATIO))
    unmapped_total = min(unmapped_total, max(0, n_rows // 3))  # 강제 배정이 전체 행수를 넘지 않도록 안전장치
    inactive_total = min(inactive_total, max(0, n_rows // 3))

    unmapped_batches = _forced_batches(unmapped_codes, unmapped_total) if unmapped_codes else {}
    inactive_batches = _forced_batches(inactive_codes, inactive_total) if inactive_codes else {}
    # 명칭불일치 코드도 최소 2행씩은 등장을 보장 (그래야 RAW 쪽 이름 변형이 실제로 남는다)
    mismatch_batches = _forced_batches(mismatch_codes, max(len(mismatch_codes) * 2, 0))

    month_start = as_of_date.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    current_month_span = max((as_of_date - month_start).days, 0)
    prev_month_span = max((prev_month_end - prev_month_start).days, 0)

    def make_row(txn_idx: int, product_code: str, operator_code: str, product_name: str) -> dict:
        if rng.random() < PREV_MONTH_TXN_RATIO:
            txn_date = prev_month_start + timedelta(days=rng.randint(0, prev_month_span))
        else:
            txn_date = month_start + timedelta(days=rng.randint(0, current_month_span))
        txn_type = TXN_TYPE_NEW if rng.random() < NEW_TXN_RATIO else TXN_TYPE_CHURN
        registered_at = datetime.combine(txn_date, datetime.min.time()) + timedelta(
            seconds=rng.randint(0, 24 * 60 * 60 - 1)
        )
        return {
            COL_TXN_ID: f"TXN{txn_idx:08d}",
            COL_TXN_DATE: txn_date,
            COL_OPERATOR_CODE: operator_code,
            COL_PRODUCT_CODE: product_code,
            COL_PRODUCT_NAME: product_name,
            COL_TXN_TYPE: txn_type,
            COL_PAYMENT_TYPE: rng.choice(PAYMENT_TYPES),
            COL_CHANNEL: rng.choice(CHANNELS),
            COL_REGISTERED_AT: registered_at,
        }

    def name_for(product_code: str) -> str:
        base_name = code_to_name.get(product_code, product_code)
        if product_code in mismatch_batches:
            return f"{base_name}(수정전)"
        return base_name

    rows = []
    txn_idx = 1

    for code, count in unmapped_batches.items():
        for _ in range(count):
            rows.append(make_row(txn_idx, code, unmapped_code_operator[code], f"미확인상품_{code}"))
            txn_idx += 1

    for code, count in inactive_batches.items():
        operator_code = code_to_operator[code]
        for _ in range(count):
            rows.append(make_row(txn_idx, code, operator_code, name_for(code)))
            txn_idx += 1

    for code, count in mismatch_batches.items():
        operator_code = code_to_operator[code]
        for _ in range(count):
            rows.append(make_row(txn_idx, code, operator_code, name_for(code)))
            txn_idx += 1

    remaining = max(0, n_rows - len(rows))
    for _ in range(remaining):
        code = rng.choice(active_codes)
        operator_code = code_to_operator[code]
        rows.append(make_row(txn_idx, code, operator_code, name_for(code)))
        txn_idx += 1

    raw_df = pd.DataFrame(rows)
    return raw_df, unmapped_codes, mismatch_codes, unmapped_code_operator


def generate_portal(
    rng: random.Random,
    raw_df: pd.DataFrame,
    as_of_date: date,
    n_perturb: int,
    n_raw_only: int,
    n_portal_only: int,
) -> tuple[pd.DataFrame, list[dict], list[dict], list[dict]]:
    """RAW를 정직하게 집계한 값을 베이스로, 포털 실적을 의도적으로 어긋나게 만든다.

    Returns:
        (portal_df, perturbed_combos, raw_only_combos, portal_only_combos)
        각 combo는 {"사업자코드": ..., "상품코드": ...} 형태.
    """
    month_start = as_of_date.replace(day=1)
    current_month_df = raw_df[
        (raw_df[COL_TXN_DATE] >= month_start) & (raw_df[COL_TXN_DATE] <= as_of_date)
    ]
    operator_name_map = {op[COL_OPERATOR_CODE]: op[COL_OPERATOR_NAME] for op in DUMMY_OPERATORS}

    pivot = (
        current_month_df.groupby([COL_OPERATOR_CODE, COL_PRODUCT_CODE, COL_TXN_TYPE])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for txn_type in (TXN_TYPE_NEW, TXN_TYPE_CHURN):
        if txn_type not in pivot.columns:
            pivot[txn_type] = 0

    product_name = (
        current_month_df.sort_values(COL_REGISTERED_AT)
        .drop_duplicates([COL_OPERATOR_CODE, COL_PRODUCT_CODE], keep="last")[
            [COL_OPERATOR_CODE, COL_PRODUCT_CODE, COL_PRODUCT_NAME]
        ]
    )

    portal_df = pivot.merge(product_name, on=[COL_OPERATOR_CODE, COL_PRODUCT_CODE], how="left")
    portal_df = portal_df.rename(columns={TXN_TYPE_NEW: COL_NEW_COUNT, TXN_TYPE_CHURN: COL_CHURN_COUNT})
    portal_df[COL_NET_COUNT] = portal_df[COL_NEW_COUNT] - portal_df[COL_CHURN_COUNT]
    portal_df[COL_OPERATOR_NAME] = portal_df[COL_OPERATOR_CODE].map(operator_name_map)
    portal_df = portal_df[
        [
            COL_OPERATOR_CODE,
            COL_OPERATOR_NAME,
            COL_PRODUCT_CODE,
            COL_PRODUCT_NAME,
            COL_NEW_COUNT,
            COL_CHURN_COUNT,
            COL_NET_COUNT,
        ]
    ]

    all_idx = list(portal_df.index)
    rng.shuffle(all_idx)

    n_perturb = min(n_perturb, len(all_idx))
    perturb_idx = all_idx[:n_perturb]
    remaining_idx = all_idx[n_perturb:]

    n_raw_only = min(n_raw_only, len(remaining_idx))
    raw_only_idx = remaining_idx[:n_raw_only]

    perturbed_combos = []
    for idx in perturb_idx:
        # 임계치(1.0%)를 확실히 넘도록, 최소 delta를 순증건수 대비 넉넉하게 준다
        current_net = max(1, int(portal_df.loc[idx, COL_NET_COUNT]))
        delta = max(2, round(current_net * 0.2)) * rng.choice([-1, 1])
        portal_df.loc[idx, COL_NEW_COUNT] = max(0, portal_df.loc[idx, COL_NEW_COUNT] + delta)
        portal_df.loc[idx, COL_NET_COUNT] = portal_df.loc[idx, COL_NEW_COUNT] - portal_df.loc[idx, COL_CHURN_COUNT]
        perturbed_combos.append(
            {
                COL_OPERATOR_CODE: portal_df.loc[idx, COL_OPERATOR_CODE],
                COL_PRODUCT_CODE: portal_df.loc[idx, COL_PRODUCT_CODE],
            }
        )

    raw_only_combos = [
        {
            COL_OPERATOR_CODE: portal_df.loc[idx, COL_OPERATOR_CODE],
            COL_PRODUCT_CODE: portal_df.loc[idx, COL_PRODUCT_CODE],
        }
        for idx in raw_only_idx
    ]
    portal_df = portal_df.drop(index=raw_only_idx).reset_index(drop=True)

    extra_rows = []
    portal_only_combos = []
    operator_codes = [op[COL_OPERATOR_CODE] for op in DUMMY_OPERATORS]
    for i in range(n_portal_only):
        operator_code = rng.choice(operator_codes)
        fake_code = f"PRDP{i + 1:05d}"
        new_count = rng.randint(3, 10)
        churn_count = rng.randint(0, 3)
        extra_rows.append(
            {
                COL_OPERATOR_CODE: operator_code,
                COL_OPERATOR_NAME: operator_name_map[operator_code],
                COL_PRODUCT_CODE: fake_code,
                COL_PRODUCT_NAME: f"포털전용상품_{fake_code}",
                COL_NEW_COUNT: new_count,
                COL_CHURN_COUNT: churn_count,
                COL_NET_COUNT: new_count - churn_count,
            }
        )
        portal_only_combos.append({COL_OPERATOR_CODE: operator_code, COL_PRODUCT_CODE: fake_code})

    portal_df = pd.concat([portal_df, pd.DataFrame(extra_rows)], ignore_index=True)
    return portal_df, perturbed_combos, raw_only_combos, portal_only_combos


def generate_all(args) -> dict:
    """더미데이터 3종 + 정답 목록을 생성해서 파일로 저장하고, 요약 정보를 반환."""
    rng = random.Random(args.seed)
    as_of_date = datetime.strptime(args.asof, "%Y-%m-%d").date()

    n_products = args.products or _default_n_products(args.rows)
    n_duplicate = args.n_duplicate if args.n_duplicate is not None else _default_count(args.rows, 8000, 3)
    n_inactive = args.n_inactive if args.n_inactive is not None else _default_count(args.rows, 4000, 6)
    n_unmapped = args.n_unmapped if args.n_unmapped is not None else _default_count(args.rows, 5000, 4)
    n_mismatch = args.n_mismatch if args.n_mismatch is not None else _default_count(args.rows, 6000, 4)
    n_compare_perturb = (
        args.n_compare_perturb if args.n_compare_perturb is not None else _default_count(args.rows, 5000, 5)
    )
    n_portal_only = args.n_portal_only if args.n_portal_only is not None else _default_count(args.rows, 10000, 3)
    n_raw_only = args.n_raw_only if args.n_raw_only is not None else _default_count(args.rows, 10000, 3)

    # 비활성/중복이 상품 수를 초과하지 않도록 방어 (rows가 아주 작을 때 대비)
    n_inactive = min(n_inactive, max(0, n_products - 1))
    n_duplicate = min(n_duplicate, max(0, n_products - n_inactive - 1))
    n_mismatch = min(n_mismatch, max(0, n_products - n_inactive))

    mapping_df, duplicated_codes, inactive_codes = generate_mapping(
        rng, n_products, n_duplicate, n_inactive, as_of_date
    )
    raw_df, unmapped_codes, mismatch_codes, _unmapped_operator = generate_raw(
        rng, mapping_df, args.rows, n_unmapped, inactive_codes, n_mismatch, as_of_date
    )
    portal_df, perturbed_combos, raw_only_combos, portal_only_combos = generate_portal(
        rng, raw_df, as_of_date, n_compare_perturb, n_raw_only, n_portal_only
    )

    out_dir = Path(args.out) if args.out else Path("benchmark/data") / str(args.rows)
    out_dir.mkdir(parents=True, exist_ok=True)

    mapping_path = out_dir / "product_mapping.xlsx"
    raw_path = out_dir / "raw_transactions.csv"
    portal_path = out_dir / "portal_performance.xlsx"
    ground_truth_path = out_dir / "ground_truth.json"

    mapping_df.to_excel(mapping_path, index=False)
    raw_df.to_csv(raw_path, index=False, encoding="utf-8-sig")
    portal_df.to_excel(portal_path, index=False)

    ground_truth = {
        "meta": {
            "rows": args.rows,
            "seed": args.seed,
            "as_of_date": args.asof,
            "n_products": n_products,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "매핑누락": sorted(unmapped_codes),
        "중복": sorted(duplicated_codes),
        "비활성사용": sorted(inactive_codes),
        "명칭불일치": sorted(mismatch_codes),
        "실적비교": {
            "perturbed": perturbed_combos,
            "raw_only": raw_only_combos,
            "portal_only": portal_only_combos,
        },
    }
    ground_truth_path.write_text(
        json.dumps(ground_truth, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    return {
        "out_dir": str(out_dir),
        "mapping_rows": len(mapping_df),
        "raw_rows": len(raw_df),
        "portal_rows": len(portal_df),
        "ground_truth": ground_truth,
    }


def main():
    args = parse_args()
    result = generate_all(args)
    print(f"생성 완료: {result['out_dir']}")
    print(f"  - 매핑표: {result['mapping_rows']}행")
    print(f"  - RAW 거래: {result['raw_rows']}행")
    print(f"  - 포털 실적: {result['portal_rows']}행")
    gt = result["ground_truth"]
    print("주입된 오류 (정답):")
    print(f"  - 매핑누락: {len(gt['매핑누락'])}건")
    print(f"  - 중복: {len(gt['중복'])}건")
    print(f"  - 비활성사용: {len(gt['비활성사용'])}건")
    print(f"  - 명칭불일치: {len(gt['명칭불일치'])}건")
    print(f"  - 실적비교(perturbed/raw_only/portal_only): "
          f"{len(gt['실적비교']['perturbed'])}/{len(gt['실적비교']['raw_only'])}/{len(gt['실적비교']['portal_only'])}건")


if __name__ == "__main__":
    main()
