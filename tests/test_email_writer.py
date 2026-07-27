"""
email_writer.py 테스트.

실제 발송은 하지 않으므로, 이메일 초안(EmailMessage)이 제목/본문/첨부를
올바르게 담고 있는지만 확인한다.
"""

from datetime import date

from src import email_writer


def test_build_email_draft_sets_subject_and_body(tmp_path):
    attachment = tmp_path / "report.txt"
    attachment.write_text("dummy content", encoding="utf-8")

    msg = email_writer.build_email_draft(
        as_of_date=date(2026, 7, 19),
        text_summary="- 실적 비교: 이상 0건",
        attachment_paths=[attachment],
    )

    assert msg["Subject"] == "[MVNO 운영팀] 7월 19일 마감 실적 공유드립니다"
    body = msg.get_body(preferencelist=("plain",)).get_content()
    assert email_writer.EMAIL_GREETING in body
    assert "- 실적 비교: 이상 0건" in body
    assert email_writer.EMAIL_CLOSING in body


def test_build_email_draft_attaches_all_files(tmp_path):
    xlsx_path = tmp_path / "report.xlsx"
    xlsx_path.write_bytes(b"xlsx-bytes")
    png_path = tmp_path / "summary.png"
    png_path.write_bytes(b"png-bytes")

    msg = email_writer.build_email_draft(
        as_of_date=date(2026, 7, 19),
        text_summary="요약 내용",
        attachment_paths=[xlsx_path, png_path],
    )

    attachments = list(msg.iter_attachments())
    filenames = {part.get_filename() for part in attachments}

    assert filenames == {"report.xlsx", "summary.png"}


def test_save_email_draft_writes_eml_file(tmp_path):
    msg = email_writer.build_email_draft(
        as_of_date=date(2026, 7, 19), text_summary="요약", attachment_paths=[]
    )
    output_path = tmp_path / "nested" / "draft.eml"

    email_writer.save_email_draft(msg, output_path)

    assert output_path.exists()
    assert b"Subject:" in output_path.read_bytes()
