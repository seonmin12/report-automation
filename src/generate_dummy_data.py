"""
더미데이터 생성 모듈.

3종의 더미파일을 만든다.
1. 포털 실적 Excel (data/portal/portal_performance.xlsx)
2. RAW 거래 CSV (data/raw/raw_transactions.csv)
3. 요금제/상품 매핑 기준표 Excel (data/mapping/product_mapping.xlsx)

검증 로직이 실제로 뭔가 잡아낼 수 있도록, 의도적으로 다음 '결함 케이스'를 섞어 넣는다.
- 매핑 기준표에 등록되지 않은 상품코드로 발생한 RAW 거래 (매핑 누락)
- 매핑 기준표에 같은 상품코드가 중복 등록된 케이스 (중복)
- 사용여부가 '비활성'인 상품코드로 발생한 RAW 거래 (비활성 상품 사용)
- 포털/RAW/매핑표에서 같은 상품코드인데 상품명이 서로 다른 케이스 (명칭 불일치)
- 포털 집계값과 RAW 집계값이 의도적으로 어긋나는 케이스 (실적 비교 대상)
"""

import pandas as pd

from config import (
    N_PRODUCTS,
    N_RAW_TRANSACTIONS,
    PORTAL_FILE,
    RAW_FILE,
    MAPPING_FILE,
    DEFAULT_AS_OF_DATE,
)


def generate_product_mapping(n_products: int = N_PRODUCTS) -> pd.DataFrame:
    """요금제/상품 매핑 기준표 더미데이터 생성.

    TODO:
    - 상품코드/표준상품명/요금제유형/사업자코드/카테고리/사용여부/매핑등록일/비고 컬럼 생성
    - 일부 상품코드를 의도적으로 중복 등록 (중복 검증용)
    - 일부 상품을 '비활성'으로 설정 (비활성 사용 검증용)
    """
    raise NotImplementedError


def generate_raw_transactions(
    mapping_df: pd.DataFrame, n_rows: int = N_RAW_TRANSACTIONS
) -> pd.DataFrame:
    """RAW 거래 데이터 더미 생성.

    TODO:
    - 거래ID/처리일자/사업자코드/상품코드/상품명/거래유형/선후불구분/채널/처리상태/등록시각 생성
    - mapping_df에 없는 상품코드를 일부 섞어서 생성 (매핑 누락 검증용)
    - mapping_df 상 비활성 상품코드도 일부 사용해서 생성 (비활성 사용 검증용)
    - 상품명을 매핑표 표준명과 다르게 일부 변형 (명칭 불일치 검증용)
    """
    raise NotImplementedError


def generate_portal_performance(raw_df: pd.DataFrame) -> pd.DataFrame:
    """포털 실적(집계) 더미 생성.

    TODO:
    - raw_df를 사업자/상품/일자 단위로 집계해서 만들되,
      일부 값을 의도적으로 어긋나게 조정 (포털-RAW 비교 검증용)
    """
    raise NotImplementedError


def main():
    mapping_df = generate_product_mapping()
    raw_df = generate_raw_transactions(mapping_df)
    portal_df = generate_portal_performance(raw_df)

    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    # TODO: mapping_df.to_excel(MAPPING_FILE, index=False)
    # TODO: raw_df.to_csv(RAW_FILE, index=False, encoding="utf-8-sig")
    # TODO: portal_df.to_excel(PORTAL_FILE, index=False)
    print("더미데이터 생성 완료 (구현 예정)")


if __name__ == "__main__":
    main()
