import base64
import re
from datetime import datetime, timedelta
from email.utils import parseaddr
from html import unescape

from sqlalchemy.orm import Session

from app.models.email import EmailAccount
from app.models.email_reply import EmailReply
from app.models.lead import Lead
from app.models.sent_email import SentEmail
from app.services.activity_logs import EVENT_REPLY_DETECTED, record_activity_log
from app.services.meeting_scheduling import (
    MeetingSchedulingServiceError,
    ensure_meeting_for_interested_reply,
)
from app.services.memory import MemoryServiceError, sync_reply_memory
from app.services.notifications import notify_new_reply
from app.services.reply_generation import (
    ReplyGenerationServiceError,
    ensure_generated_reply,
)
from app.services.reply_classification import (
    ReplyClassificationServiceError,
    ensure_reply_classification,
)
from app.services.gmail_sender import GmailSendServiceError, gmail_api_request

_GMAIL_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
_GMAIL_GET_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
_NON_REGRESSION_LEAD_STATUSES = {"MEETING_SCHEDULED", "CLOSED"}


class ReplyDetectionServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _decode_base64_data(value: str | None) -> str:
    if not value:
        return ""

    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode((value + padding).encode("utf-8"))
    except Exception:
        return ""
    return decoded.decode("utf-8", errors="ignore").strip()


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_body_from_part(part: dict) -> tuple[str, str]:
    mime_type = (part.get("mimeType") or "").lower()
    body_data = _decode_base64_data((part.get("body") or {}).get("data"))
    plain_text = ""
    html_text = ""

    if mime_type == "text/plain" and body_data:
        plain_text = body_data
    elif mime_type == "text/html" and body_data:
        html_text = _strip_html(body_data)

    for child in part.get("parts") or []:
        child_plain, child_html = _extract_body_from_part(child)
        if child_plain and not plain_text:
            plain_text = child_plain
        if child_html and not html_text:
            html_text = child_html

    return plain_text, html_text


def _extract_reply_body(message: dict) -> str:
    payload = message.get("payload") or {}
    plain_text, html_text = _extract_body_from_part(payload)
    body = plain_text or html_text or (message.get("snippet") or "").strip()
    return body[:10000]


def _header_map(message: dict) -> dict[str, str]:
    headers = ((message.get("payload") or {}).get("headers") or [])
    return {
        (header.get("name") or "").lower(): header.get("value") or ""
        for header in headers
    }


def _extract_sender_email(message: dict) -> str | None:
    from_header = _header_map(message).get("from", "")
    _, email_address = parseaddr(from_header)
    email_address = email_address.strip().lower()
    return email_address or None


def _message_received_at(message: dict) -> datetime:
    internal_date = message.get("internalDate")
    if internal_date:
        try:
            return datetime.utcfromtimestamp(int(internal_date) / 1000)
        except (TypeError, ValueError):
            pass
    return datetime.utcnow()


def _list_recent_inbox_message_ids(db: Session, account: EmailAccount) -> list[str]:
    max_pages = 3
    max_results = 100
    page_token = None
    message_ids: list[str] = []

    for _ in range(max_pages):
        params: list[tuple[str, str | int]] = [
            ("labelIds", "INBOX"),
            ("maxResults", max_results),
        ]
        if page_token:
            params.append(("pageToken", page_token))

        response = gmail_api_request(
            db=db,
            account=account,
            method="GET",
            url=_GMAIL_LIST_URL,
            feature="gmail_list_messages",
            params=params,
        )
        if response.status_code != 200:
            detail = response.text.strip() or "Unknown Gmail list error."
            raise ReplyDetectionServiceError(
                f"Failed to list Gmail inbox messages: {detail}",
                status_code=502,
            )

        payload = response.json()
        items = payload.get("messages") or []
        message_ids.extend(
            item["id"] for item in items if isinstance(item, dict) and item.get("id")
        )
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return message_ids


def _get_message(db: Session, account: EmailAccount, message_id: str) -> dict:
    response = gmail_api_request(
        db=db,
        account=account,
        method="GET",
        url=_GMAIL_GET_URL.format(message_id=message_id),
        feature="gmail_get_message",
        params={"format": "full"},
    )
    if response.status_code != 200:
        detail = response.text.strip() or "Unknown Gmail message error."
        raise ReplyDetectionServiceError(
            f"Failed to fetch Gmail message `{message_id}`: {detail}",
            status_code=502,
        )
    return response.json()


def _find_lead_for_message(
    db: Session, account: EmailAccount, message: dict
) -> Lead | None:
    thread_id = message.get("threadId")
    if thread_id:
        sent_email = (
            db.query(SentEmail)
            .filter(
                SentEmail.email_account_id == account.id,
                SentEmail.thread_id == thread_id,
            )
            .order_by(SentEmail.sent_at.desc())
            .first()
        )
        if sent_email:
            return db.query(Lead).filter(Lead.id == sent_email.lead_id).first()

    sender_email = _extract_sender_email(message)
    if not sender_email:
        return None

    return (
        db.query(Lead)
        .filter(
            Lead.workspace_id == account.workspace_id,
            Lead.email.ilike(sender_email),
        )
        .first()
    )


def _latest_reply_timestamp(db: Session, account: EmailAccount) -> datetime:
    latest_reply = (
        db.query(EmailReply)
        .filter(EmailReply.email_account_id == account.id)
        .order_by(EmailReply.received_at.desc())
        .first()
    )
    if latest_reply:
        return latest_reply.received_at

    latest_sent = (
        db.query(SentEmail)
        .filter(SentEmail.email_account_id == account.id)
        .order_by(SentEmail.sent_at.desc())
        .first()
    )
    if latest_sent:
        return latest_sent.sent_at

    return account.connected_at


def poll_gmail_replies_for_account(db: Session, account: EmailAccount) -> dict[str, int]:
    try:
        message_ids = _list_recent_inbox_message_ids(db, account)
    except GmailSendServiceError as exc:
        raise ReplyDetectionServiceError(str(exc), status_code=exc.status_code) from exc

    newest_known = _latest_reply_timestamp(db, account) - timedelta(hours=12)
    stored = 0
    memories_indexed = 0
    memory_failures = 0
    classified = 0
    classification_failed = 0
    meetings_created = 0
    meeting_failures = 0
    generated = 0
    generation_failed = 0
    skipped = 0

    for message_id in message_ids:
        already_seen = (
            db.query(EmailReply)
            .filter(
                EmailReply.email_account_id == account.id,
                EmailReply.message_id == message_id,
            )
            .first()
        )
        if already_seen:
            skipped += 1
            continue

        message = _get_message(db, account, message_id)
        received_at = _message_received_at(message)
        if received_at < newest_known:
            skipped += 1
            continue

        sender_email = _extract_sender_email(message)
        if sender_email and sender_email == account.email_address.lower():
            skipped += 1
            continue

        lead = _find_lead_for_message(db, account, message)
        if not lead:
            skipped += 1
            continue

        reply_body = _extract_reply_body(message)
        if not reply_body:
            skipped += 1
            continue

        reply = EmailReply(
            lead_id=lead.id,
            email_account_id=account.id,
            message_id=message_id,
            thread_id=message.get("threadId"),
            reply_body=reply_body,
            received_at=received_at,
        )
        db.add(reply)

        if lead.status not in _NON_REGRESSION_LEAD_STATUSES:
            lead.status = "REPLIED"

        db.flush()
        record_activity_log(
            db,
            workspace_id=lead.workspace_id,
            lead_id=lead.id,
            event_type=EVENT_REPLY_DETECTED,
            message=f"Detected reply from {lead.email}.",
            metadata={
                "reply_id": reply.id,
                "message_id": reply.message_id,
                "thread_id": reply.thread_id,
                "email_account_id": account.id,
            },
        )
        notify_new_reply(
            db,
            workspace_id=lead.workspace_id,
            lead_id=lead.id,
            lead_name=lead.name,
            lead_email=lead.email,
            reply_id=reply.id,
            message_id=reply.message_id,
            thread_id=reply.thread_id,
            reply_body=reply.reply_body,
        )
        try:
            sync_reply_memory(db, lead.workspace_id, reply)
            memories_indexed += 1
        except MemoryServiceError:
            memory_failures += 1

        try:
            classification = ensure_reply_classification(db, reply)
            classified += 1
        except ReplyClassificationServiceError:
            classification_failed += 1
            classification = None

        meeting_link = None
        if classification:
            try:
                meeting = ensure_meeting_for_interested_reply(db, reply, classification)
                if meeting:
                    meeting_link = meeting.meeting_link
                    meetings_created += 1
            except MeetingSchedulingServiceError:
                meeting_failures += 1

            try:
                generated_reply = ensure_generated_reply(
                    db,
                    reply,
                    classification,
                    meeting_link=meeting_link,
                )
                if generated_reply:
                    generated += 1
            except ReplyGenerationServiceError:
                generation_failed += 1
        stored += 1

    return {
        "stored": stored,
        "memories_indexed": memories_indexed,
        "memory_failures": memory_failures,
        "classified": classified,
        "classification_failed": classification_failed,
        "meetings_created": meetings_created,
        "meeting_failures": meeting_failures,
        "generated": generated,
        "generation_failed": generation_failed,
        "skipped": skipped,
    }
