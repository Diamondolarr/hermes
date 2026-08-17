from dataclasses import dataclass
import base64
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.admin_monitoring import record_api_usage
from app.models.email import EmailAccount
from app.utils.crypto import InvalidToken, decrypt_value, encrypt_value

_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GmailSendServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class GmailSendResult:
    message_id: str
    thread_id: str | None
    email_account_id: str


def _get_gmail_account(db: Session, workspace_id: str) -> EmailAccount:
    account = (
        db.query(EmailAccount)
        .filter(
            EmailAccount.workspace_id == workspace_id,
            EmailAccount.provider == "gmail",
        )
        .order_by(EmailAccount.connected_at.desc())
        .first()
    )
    if not account:
        raise GmailSendServiceError(
            "Connect a Gmail account before sending email.", status_code=400
        )
    return account


def get_latest_gmail_account(db: Session, workspace_id: str) -> EmailAccount:
    return _get_gmail_account(db, workspace_id)


def _decrypt_token(value: str, field_name: str) -> str:
    try:
        return decrypt_value(value)
    except ValueError as exc:
        raise GmailSendServiceError(
            "ENCRYPTION_KEY is not configured.", status_code=500
        ) from exc
    except InvalidToken as exc:
        raise GmailSendServiceError(
            f"Stored Gmail {field_name} could not be decrypted.", status_code=500
        ) from exc


def _build_raw_message(
    *, from_email: str, to_email: str, subject: str, body: str
) -> str:
    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


def _send_with_access_token(access_token: str, raw_message: str) -> httpx.Response:
    with httpx.Client(timeout=20) as client:
        return client.post(
            _GMAIL_SEND_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"raw": raw_message},
        )


def _request_with_access_token(
    access_token: str,
    method: str,
    url: str,
    *,
    params: dict | list[tuple[str, str | int]] | None = None,
    json: dict | None = None,
    data: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> httpx.Response:
    request_headers = {"Authorization": f"Bearer {access_token}"}
    if headers:
        request_headers.update(headers)

    with httpx.Client(timeout=timeout) as client:
        return client.request(
            method,
            url,
            params=params,
            json=json,
            data=data,
            headers=request_headers,
        )


def _refresh_access_token(db: Session, account: EmailAccount) -> str:
    if not settings.google_client_id or not settings.google_client_secret:
        raise GmailSendServiceError(
            "Google OAuth is not configured.", status_code=500
        )

    refresh_token = _decrypt_token(account.refresh_token, "refresh token")
    token_data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    with httpx.Client(timeout=20) as client:
        response = client.post(
            _GOOGLE_TOKEN_URL,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise GmailSendServiceError(
            "Failed to refresh Gmail access token.", status_code=502
        )

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise GmailSendServiceError(
            "Google token refresh did not return an access token.",
            status_code=502,
        )

    try:
        account.access_token = encrypt_value(access_token)
        if payload.get("refresh_token"):
            account.refresh_token = encrypt_value(payload["refresh_token"])
    except ValueError as exc:
        raise GmailSendServiceError(
            "ENCRYPTION_KEY is not configured.", status_code=500
        ) from exc

    db.flush()
    return access_token


def gmail_api_request(
    *,
    db: Session,
    account: EmailAccount,
    method: str,
    url: str,
    feature: str = "gmail_api",
    params: dict | list[tuple[str, str | int]] | None = None,
    json: dict | None = None,
    data: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> httpx.Response:
    try:
        access_token = _decrypt_token(account.access_token, "access token")
    except GmailSendServiceError:
        access_token = _refresh_access_token(db, account)

    response = _request_with_access_token(
        access_token,
        method,
        url,
        params=params,
        json=json,
        data=data,
        headers=headers,
        timeout=timeout,
    )
    if response.status_code == 401:
        access_token = _refresh_access_token(db, account)
        response = _request_with_access_token(
            access_token,
            method,
            url,
            params=params,
            json=json,
            data=data,
            headers=headers,
            timeout=timeout,
        )
    record_api_usage(
        db,
        workspace_id=account.workspace_id,
        provider="gmail",
        feature=feature,
        model_name="gmail-api",
        success=response.status_code < 400,
        metadata={
            "method": method,
            "url": url,
            "status_code": response.status_code,
            "email_account_id": account.id,
        },
    )
    return response


def send_gmail_message(
    *,
    db: Session,
    workspace_id: str,
    to_email: str,
    subject: str,
    body: str,
) -> GmailSendResult:
    account = _get_gmail_account(db, workspace_id)
    raw_message = _build_raw_message(
        from_email=account.email_address,
        to_email=to_email,
        subject=subject,
        body=body,
    )

    response = gmail_api_request(
        db=db,
        account=account,
        method="POST",
        url=_GMAIL_SEND_URL,
        feature="gmail_send_message",
        json={"raw": raw_message},
        headers={"Content-Type": "application/json"},
    )

    if response.status_code not in (200, 202):
        detail = response.text.strip() or "Unknown Gmail API error."
        raise GmailSendServiceError(
            f"Gmail send failed: {detail}", status_code=502
        )

    payload = response.json()
    message_id = payload.get("id")
    if not message_id:
        raise GmailSendServiceError(
            "Gmail API did not return a message id.", status_code=502
        )
    return GmailSendResult(
        message_id=message_id,
        thread_id=payload.get("threadId"),
        email_account_id=account.id,
    )
