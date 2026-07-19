# 실적 데이터 검증 및 리포트 자동화 (MVNO 통신사 사무보조 업무 자동화 프로젝트)

> ⚠️ 본 프로젝트는 포트폴리오 목적으로 제작되었으며, 모든 데이터는 100% 더미(가상)입니다.
> 실제 회사명, 파트너명, 상품명, 컬럼명을 사용하지 않았습니다.

## 배경

통신사 MVNO(알뜰폰) 전략팀에서 반복적으로 수행하는 다음 업무를 자동화 대상으로 삼았습니다.

- 실시간 실적 공지 (포털 실적 vs RAW 데이터 대사)
- 요금제/상품 미매핑 현황 점검
- 사업자별 누적 가입자 집계 (규제기관 제출용)

기존에는 통합 실적 포털/데이터레이크에서 엑셀·CSV를 내려받아 장표에 붙여넣고,
결과를 엑셀 화면 캡처(비트맵)와 텍스트 요약으로 Teams에 공유하는 방식으로 처리하던 업무입니다.
이 프로젝트는 그 흐름을 Python 스크립트로 재현합니다.

## TODO (진행 중)

- [ ] 더미데이터 생성기 구현
- [ ] 당월 누적 집계 로직 구현
- [ ] 포털-RAW 비교 로직 구현
- [ ] 매핑 검증 로직 구현 (누락/중복/비활성/명칭불일치)
- [ ] Excel 검증 리포트 생성
- [ ] txt 요약 생성
- [ ] 요약 이미지(PNG) 생성
- [ ] 파이프라인 통합 (main.py)
- [ ] 테스트 작성
- [ ] 실행 결과 스크린샷 및 최종 설명 추가

## 기술 스택

- Python 3.11+
- pandas, numpy (데이터 처리 및 더미데이터 생성)
- openpyxl (Excel 리포트 생성 및 스타일링)
- matplotlib / Pillow (요약 이미지 생성)
- pytest (검증 로직 테스트)
- (확장) FastAPI + Vercel (웹 서비스화, 2단계)

## 폴더 구조

```
mvno-report-automation/
├── README.md
├── requirements.txt
├── config.py
├── data/
│   ├── portal/       # 포털 실적 Excel 더미
│   ├── raw/          # RAW 데이터 CSV 더미
│   └── mapping/       # 요금제/상품 매핑 기준표 Excel 더미
├── src/
│   ├── generate_dummy_data.py
│   ├── aggregate.py
│   ├── compare.py
│   ├── validate.py
│   ├── report_builder.py
│   ├── summary_writer.py
│   └── image_builder.py
├── output/            # 실행 결과물 (xlsx, txt, png)
├── main.py
└── tests/
    └── test_validate.py
```

## 실행 방법 (구현 완료 후 작성 예정)

```bash
pip install -r requirements.txt
python main.py --asof 2026-07-19
```

## 실무 대응 관계

| 실무 업무 | 프로젝트 기능 |
|---|---|
| 실시간 실적 공지 | 포털 vs RAW 비교 리포트 (compare.py) |
| 요금제 미매핑 현황 | 매핑 검증 4종 (validate.py) |
| 과기부 제출자료(사업자별 누적가입자) | 당월 누적 집계 (aggregate.py) |

## 면접 설명 포인트 (요약)

- 수기로 하던 포털-RAW 대사 작업을 pandas 기반 자동 검증 로직으로 재구성
- 매핑 무결성(누락/중복/비활성/명칭불일치) 검증 로직 직접 설계
- openpyxl로 실무형 Excel 리포트, matplotlib으로 Teams 공유용 요약 이미지까지 실제 업무 흐름 재현
