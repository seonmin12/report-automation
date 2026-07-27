"""
실적 검증 결과 공유 이메일 초안(.eml) 생성 모듈.

사내에서 매번 같은 문구로 반복 발송하던 실적 공유 메일("안녕하십니까 MVNO 운영팀입니다.
...마감 실적 공유드립니다. 감사합니다.")을 재현한다. 사내 메일 서버 인증정보를 다루거나
실제로 메일을 발송하는 것은 보안상 이 스크립트의 범위 밖이며, 제목/본문/첨부까지 채워진
.eml 파일만 만든다. 메일 클라이언트(Outlook, Mail 등)에서 더블클릭으로 열어 '보내기'만
누르면 되는 상태로 준비하는 것이 목표다.
"""

from datetime import date
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path

EMAIL_SUBJECT_TEMPLATE = "[MVNO 운영팀] {month}월 {day}일 마감 실적 공유드립니다"
EMAIL_GREETING = "안녕하십니까, MVNO 운영팀입니다."
EMAIL_CLOSING = "감사합니다."

# 실제 수신자가 아닌 예시 주소. 실사용 시 담당자 주소로 교체해서 쓴다.
DEFAULT_SENDER = "mvno-strategy-team@example.com"
DEFAULT_RECIPIENTS = ["partner-ops-team@example.com"]

_MIME_TYPES_BY_SUFFIX = {
    ".xlsx": ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ".png": ("image", "png"),
    ".txt": ("text", "plain"),
}


def _guess_mime_type(path: Path) -> tuple[str, str]:
    return _MIME_TYPES_BY_SUFFIX.get(path.suffix.lower(), ("application", "octet-stream"))


def build_email_draft(
    as_of_date: date,
    text_summary: str,
    attachment_paths: list,
    sender: str = DEFAULT_SENDER,
    recipients: list | None = None,
) -> EmailMessage:
    """실적 요약 이메일 초안을 EmailMessage 객체로 조립 (실제 발송은 하지 않음)."""
    recipients = recipients or DEFAULT_RECIPIENTS

    msg = EmailMessage()
    msg["Subject"] = EMAIL_SUBJECT_TEMPLATE.format(month=as_of_date.month, day=as_of_date.day)
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(f"{EMAIL_GREETING}\n\n{text_summary}\n\n{EMAIL_CLOSING}")

    for attachment_path in attachment_paths:
        attachment_path = Path(attachment_path)
        maintype, subtype = _guess_mime_type(attachment_path)
        msg.add_attachment(
            attachment_path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment_path.name,
        )

    return msg


def save_email_draft(msg: EmailMessage, output_path):
    """이메일 초안을 .eml 파일로 저장. 메일 클라이언트에서 더블클릭하면 바로 열린다."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(msg))
