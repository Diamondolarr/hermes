from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.email import EmailAccount
from app.models.lead import Lead
from app.models.scheduled_email import ScheduledEmail
from app.models.sent_email import SentEmail
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.approvals import EmailDispatchResponse
from app.services.activity_logs import EVENT_EMAIL_SENT, record_activity_log
from app.services.email_generation import EmailGenerationServiceError
from app.services.gmail_sender import GmailSendServiceError, send_gmail_message
from app.services.insight_pipeline import ensure_generated_email
from app.services.lead_research import LeadResearchServiceError
from app.services.memory import MemoryServiceError, sync_sent_email_memory
from app.services.notifications import notify_system_error
from app.services.sales_insight import SalesInsightServiceError
from app.utils.auth import get_current_user
from app.utils.crypto import encrypt_value

router = APIRouter()

_GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def _create_oauth_state(user_id: str, workspace_id: str) -> str:
    payload = {
        "sub": user_id,
        "workspace_id": workspace_id,
        "typ": "oauth_state",
        "exp": datetime.utcnow() + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_oauth_state(state: str) -> dict:
    payload = jwt.decode(
        state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    if payload.get("typ") != "oauth_state":
        raise JWTError("Invalid state token.")
    return payload


@router.get("/gmail/connect")
def gmail_connect(current=Depends(get_current_user)) -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured.",
        )

    user, workspace = current
    state = _create_oauth_state(user.id, workspace.id)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(_GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    url = f"{_GMAIL_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/gmail/callback")
def gmail_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state.")

    try:
        payload = _decode_oauth_state(state)
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid state token.")

    user_id = payload.get("sub")
    workspace_id = payload.get("workspace_id")
    if not user_id or not workspace_id:
        raise HTTPException(status_code=400, detail="Invalid state token.")

    user = (
        db.query(User)
        .filter(User.id == user_id, User.workspace_id == workspace_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid state token.")

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=400, detail="Workspace not found.")

    token_data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }

    with httpx.Client(timeout=10) as client:
        token_resp = client.post(
            _GMAIL_TOKEN_URL, data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Token exchange failed.")
        token_json = token_resp.json()

        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Token exchange failed.")

        userinfo_resp = client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user profile.")
        userinfo = userinfo_resp.json()

    email_address = userinfo.get("email")
    if not email_address:
        raise HTTPException(status_code=400, detail="Email address not available.")

    account = (
        db.query(EmailAccount)
        .filter(
            EmailAccount.workspace_id == workspace_id,
            EmailAccount.provider == "gmail",
            EmailAccount.email_address == email_address,
        )
        .first()
    )

    try:
        encrypted_access = encrypt_value(access_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ENCRYPTION_KEY is not configured.",
        )

    if account:
        account.access_token = encrypted_access
        if refresh_token:
            account.refresh_token = encrypt_value(refresh_token)
        account.connected_at = datetime.utcnow()
    else:
        if not refresh_token:
            raise HTTPException(
                status_code=400,
                detail="Refresh token not returned. Try reconnecting with consent.",
            )
        account = EmailAccount(
            workspace_id=workspace_id,
            provider="gmail",
            access_token=encrypted_access,
            refresh_token=encrypt_value(refresh_token),
            email_address=email_address,
        )
        db.add(account)

    db.commit()
    return {"message": "Gmail account connected.", "email_address": email_address}


@router.post("/send/{campaign_id}/{lead_id}", response_model=EmailDispatchResponse)
def send_email(
    campaign_id: str,
    lead_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailDispatchResponse:
    _, workspace = current

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.workspace_id == workspace.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.workspace_id == workspace.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    existing_initial_schedule = (
        db.query(ScheduledEmail)
        .filter(
            ScheduledEmail.lead_id == lead.id,
            ScheduledEmail.campaign_id == campaign.id,
            ScheduledEmail.step_number == 0,
        )
        .first()
    )
    if existing_initial_schedule and existing_initial_schedule.status == "SENT":
        raise HTTPException(status_code=409, detail="Initial email has already been sent.")

    try:
        generated_email = ensure_generated_email(db, workspace.id, lead, campaign)
    except (
        EmailGenerationServiceError,
        LeadResearchServiceError,
        SalesInsightServiceError,
    ) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if workspace.human_approval_enabled:
        if existing_initial_schedule:
            scheduled_email = existing_initial_schedule
            scheduled_email.email_type = "INITIAL"
            scheduled_email.draft_subject = generated_email.subject
            scheduled_email.draft_body = generated_email.body
            scheduled_email.scheduled_for = datetime.utcnow()
            scheduled_email.status = "PENDING"
            scheduled_email.approval_status = "PENDING_APPROVAL"
            scheduled_email.approved_by_user_id = None
            scheduled_email.approved_at = None
            scheduled_email.rejected_by_user_id = None
            scheduled_email.rejected_at = None
            scheduled_email.rejection_reason = None
        else:
            scheduled_email = ScheduledEmail(
                lead_id=lead.id,
                campaign_id=campaign.id,
                step_number=0,
                email_type="INITIAL",
                draft_subject=generated_email.subject,
                draft_body=generated_email.body,
                scheduled_for=datetime.utcnow(),
                status="PENDING",
                approval_status="PENDING_APPROVAL",
            )
            db.add(scheduled_email)

        db.commit()
        db.refresh(scheduled_email)
        return EmailDispatchResponse(
            lead_id=lead.id,
            campaign_id=campaign.id,
            status="PENDING_APPROVAL",
            message="Email queued for human approval.",
            scheduled_email_id=scheduled_email.id,
            approval_status=scheduled_email.approval_status,
        )

    if existing_initial_schedule and existing_initial_schedule.status in {"PENDING", "QUEUED"}:
        raise HTTPException(
            status_code=409,
            detail="Initial email is already queued. Approve or clear the scheduled item first.",
        )

    try:
        send_result = send_gmail_message(
            db=db,
            workspace_id=workspace.id,
            to_email=lead.email,
            subject=generated_email.subject,
            body=generated_email.body,
        )
    except GmailSendServiceError as exc:
        failed_email = SentEmail(
            lead_id=lead.id,
            campaign_id=campaign.id,
            message_id=None,
            status="FAILED",
        )
        db.add(failed_email)
        notify_system_error(
            db,
            workspace_id=workspace.id,
            title="Manual email send failed",
            body=f"Could not send email to {lead.email} for campaign {campaign.name}.",
            metadata={
                "campaign_id": campaign.id,
                "lead_id": lead.id,
                "error": str(exc),
            },
            resource_type="manual_send",
            resource_id=f"{campaign.id}:{lead.id}",
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    sent_email = SentEmail(
        lead_id=lead.id,
        campaign_id=campaign.id,
        email_account_id=send_result.email_account_id,
        message_id=send_result.message_id,
        thread_id=send_result.thread_id,
        email_subject=generated_email.subject,
        email_body=generated_email.body,
        status="SENT",
    )
    db.add(sent_email)
    db.flush()
    try:
        sync_sent_email_memory(db, workspace.id, sent_email)
    except MemoryServiceError:
        pass
    record_activity_log(
        db,
        workspace_id=workspace.id,
        lead_id=lead.id,
        campaign_id=campaign.id,
        event_type=EVENT_EMAIL_SENT,
        message=f"Sent email to {lead.email} for campaign {campaign.name}.",
        metadata={
            "sent_email_id": sent_email.id,
            "message_id": sent_email.message_id,
            "subject": sent_email.email_subject,
            "delivery_mode": "manual",
        },
    )
    db.commit()
    db.refresh(sent_email)

    return EmailDispatchResponse(
        lead_id=sent_email.lead_id,
        campaign_id=sent_email.campaign_id,
        status=sent_email.status,
        message="Email sent successfully.",
        sent_email_id=sent_email.id,
        message_id=sent_email.message_id,
        sent_at=sent_email.sent_at,
    )
