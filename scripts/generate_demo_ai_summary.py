"""
데모 job용 AI 요약을 실제 Claude API로 한 번 생성해서 정적 파일로 저장하는 스크립트.

왜 런타임에 호출하지 않고 미리 생성해서 저장하는가
----------------------------------------------------
이 프로젝트는 인증 없는 공개 데모다. 결과 화면에 "AI 요약 보기" 버튼을 만들어서
매 요청마다 실제 LLM API를 호출하면, 방문자가 버튼을 누를 때마다 이 스크립트를
실행한 사람의 API 키로 과금된다. 게다가 데모 job의 입력 데이터는 고정 시드로
만든 더미데이터라 매번 계산해도 사실상 같은 내용이 나온다 — 매번 새로 호출할
이유가 없다.

그래서 이 스크립트는 딱 한 번, 로컬에서 실제 API 키로 실행해서 결과를
`web/static_data/demo_ai_summary.json`에 저장해 둔다. 배포된 웹 서비스
(`web/app.py`의 `/api/ai-summary/{job_id}`)는 이 파일을 그대로 읽어서 보여줄
뿐, 요청이 들어올 때 API를 호출하지 않는다. 업로드한 파일(실제 사용자 데이터)에는
이 기능 자체를 제공하지 않는다 — 매번 다른 데이터라 미리 구워둘 수 없고,
라이브로 열면 같은 과금 문제가 다시 생기기 때문이다.

사용법
------
    cp .env.example .env        # .env에 ANTHROPIC_API_KEY=sk-ant-... 채워넣기
    pip install anthropic python-dotenv
    python scripts/generate_demo_ai_summary.py

    # 또는 .env 없이 바로:
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/generate_demo_ai_summary.py

`anthropic`/`python-dotenv` 패키지는 이 스크립트를 실행할 때만 필요하다. 배포되는
웹 서비스는 정적 파일만 읽으므로 `requirements.txt`(Vercel 배포에 쓰이는 의존성
목록)에는 넣지 않았다. `.env`는 `.gitignore` 처리되어 있어 실수로 커밋될 걱정은
없다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv  # .env에 ANTHROPIC_API_KEY를 넣어뒀다면 자동으로 읽는다

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass  # python-dotenv 없으면 그냥 시스템 환경변수만 본다 (export로 직접 설정한 경우)

import config
from src import aggregate, compare, generate_dummy_data, report_builder, summary_writer, validate

MODEL = "claude-sonnet-5"
OUTPUT_PATH = REPO_ROOT / "web" / "static_data" / "demo_ai_summary.json"


def build_demo_context() -> dict:
    """web/app.py의 _get_or_create_demo_job()과 완전히 동일한 방식으로 데모 데이터를 만든다."""
    as_of_date = config.DEFAULT_AS_OF_DATE
    mapping_df = generate_dummy_data.generate_product_mapping()
    raw_df = generate_dummy_data.generate_raw_transactions(mapping_df)
    portal_df = generate_dummy_data.generate_portal_performance(raw_df)

    monthly_df = aggregate.filter_current_month(raw_df, as_of_date)
    operator_product_df = aggregate.aggregate_by_operator_product(monthly_df)
    operator_summary_df = aggregate.aggregate_by_operator(monthly_df)

    compare_df = compare.compare_portal_vs_raw(portal_df, operator_product_df)
    validation_results = validate.run_all_validations(raw_df, portal_df, mapping_df)
    operator_summary_df = aggregate.attach_validation_status(
        operator_summary_df, compare_df, validation_results
    )
    error_detail_df = report_builder.build_error_detail_df(compare_df, validation_results)
    text_summary = summary_writer.build_text_summary(
        as_of_date, compare_df, validation_results, operator_summary_df
    )

    return {
        "as_of_date": as_of_date,
        "text_summary": text_summary,
        "operator_summary_df": operator_summary_df,
        "error_detail_df": error_detail_df,
    }


def build_prompt(ctx: dict) -> str:
    operator_table = ctx["operator_summary_df"].to_string(index=False)
    error_rows = ctx["error_detail_df"].to_string(index=False) if not ctx["error_detail_df"].empty else "(없음)"

    return f"""당신은 MVNO 사업 운영팀의 데이터 분석가입니다. 아래는 {ctx['as_of_date']:%Y-%m-%d} 기준
실적 검증 파이프라인이 계산한 결과입니다. 이 내용을 팀장에게 보고하는 것처럼, 자연스러운
한국어 비즈니스 문체로 5~7문장짜리 요약을 작성해주세요.

- 기계적인 항목 나열이 아니라, 어떤 사업자/이슈가 특히 주의가 필요한지 자연스럽게 짚어주세요.
- 구체적인 사업자명과 숫자를 인용해 근거를 보여주세요.
- 과장하지 말고, 데이터에 있는 사실만 이야기하세요.
- 마지막 문장은 다음 담당자가 무엇을 확인하면 좋을지 짧은 제안으로 마무리하세요.

[규칙 기반 요약]
{ctx['text_summary']}

[사업자별 요약 표]
{operator_table}

[오류상세 표]
{error_rows}
"""


def main():
    try:
        import anthropic
    except ImportError:
        print("anthropic 패키지가 없습니다. 먼저 `pip install anthropic`를 실행하세요.")
        raise SystemExit(1)

    ctx = build_demo_context()
    prompt = build_prompt(ctx)

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수를 자동으로 읽음
    response = client.messages.create(
        model=MODEL,
        max_tokens=1200,  # 한글 5~7문장이 토큰을 예상보다 많이 먹어서, 첫 시도(600)에서 문장 중간에 잘렸었음
        messages=[{"role": "user", "content": prompt}],
    )
    summary_text = "".join(block.text for block in response.content if block.type == "text").strip()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "summary": summary_text,
                "model": MODEL,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "as_of_date": ctx["as_of_date"].isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"저장 완료: {OUTPUT_PATH}")
    print()
    print(summary_text)


if __name__ == "__main__":
    main()
