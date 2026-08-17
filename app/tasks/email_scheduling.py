from datetime import datetime

from celery.exceptions import Retry

from app.db.session import SessionLocal
from app.models.campaign import Campaign
from app.models.followup import Followup
from app.models.lead import Lead
from app.models.scheduled_email import ScheduledEmail
from app.models.sent_email import SentEmail
from app.services.activity_logs import EVENT_EMAIL_SENT, record_activity_log
from app.services.gmail_sender import GmailSendServiceError, send_gmail_message
from app.services.insight_pipeline import ensure_generated_email
from app.services.memory import MemoryServiceError, sync_sent_email_memory
from app.services.notifications import notify_system_error
from app.tasks.celery_app import celery_app


@celery_app.task(
    name="app.tasks.dispatch_due_scheduled_emails",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def dispatch_due_scheduled_emails() -> dict[str, int]:
    db = SessionLocal()
    try:
        due_items = (
            db.query(ScheduledEmail)
            .filter(
                ScheduledEmail.status == "PENDING",
                ScheduledEmail.approval_status == "APPROVED",
                ScheduledEmail.scheduled_for <= datetime.utcnow(),
            )
            .order_by(ScheduledEmail.scheduled_for.asc())
            .all()
        )

        queued = 0
        for item in due_items:
            item.status = "QUEUED"
            db.flush()
            send_scheduled_email_task.delay(item.id)
            queued += 1

        db.commit()
        return {"queued": queued}
    finally:
        db.close()


@celery_app.task(name="app.tasks.send_scheduled_email", bind=True, max_retries=3)
def send_scheduled_email_task(self, scheduled_email_id: str) -> dict[str, str]:
    db = SessionLocal()
    scheduled_email: ScheduledEmail | None = None
    lead: Lead | None = None
    campaign: Campaign | None = None
    try:
        scheduled_email = (
            db.query(ScheduledEmail)
            .filter(ScheduledEmail.id == scheduled_email_id)
            .first()
        )
        if not scheduled_email:
            return {"status": "missing"}
        if scheduled_email.status == "SENT":
            return {"status": "already_sent"}

        lead = db.query(Lead).filter(Lead.id == scheduled_email.lead_id).first()
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == scheduled_email.campaign_id)
            .first()
        )
        if not lead or not campaign:
            scheduled_email.status = "FAILED"
            if lead:
                notify_system_error(
                    db,
                    workspace_id=lead.workspace_id,
                    title="Scheduled email could not be processed",
                    body="A scheduled email could not be processed because the lead or campaign record was missing.",
                    metadata={
                        "scheduled_email_id": scheduled_email.id,
                        "lead_id": scheduled_email.lead_id,
                        "campaign_id": scheduled_email.campaign_id,
                    },
                    resource_type="scheduled_email",
                    resource_id=scheduled_email.id,
                )
            db.commit()
            return {"status": "failed", "error": "Lead or campaign not found."}

        if scheduled_email.draft_subject and scheduled_email.draft_body:
            subject = scheduled_email.draft_subject
            body = scheduled_email.draft_body
        elif scheduled_email.step_number == 0:
            draft = ensure_generated_email(db, campaign.workspace_id, lead, campaign)
            subject = draft.subject
            body = draft.body
        else:
            followup = (
                db.query(Followup)
                .filter(
                    Followup.lead_id == lead.id,
                    Followup.campaign_id == campaign.id,
                    Followup.step_number == scheduled_email.step_number,
                )
                .first()
            )
            if not followup:
                scheduled_email.status = "FAILED"
                notify_system_error(
                    db,
                    workspace_id=campaign.workspace_id,
                    title="Scheduled follow-up content missing",
                    body=(
                        f"Follow-up step {scheduled_email.step_number} for campaign "
                        f"{campaign.name} could not be sent because its content was missing."
                    ),
                    metadata={
                        "scheduled_email_id": scheduled_email.id,
                        "campaign_id": campaign.id,
                        "lead_id": lead.id,
                        "step_number": scheduled_email.step_number,
                    },
                    resource_type="scheduled_email",
                    resource_id=scheduled_email.id,
                )
                db.commit()
                return {"status": "failed", "error": "Follow-up content not found."}

            subject = followup.email_subject
            body = followup.email_body

        send_result = send_gmail_message(
            db=db,
            workspace_id=campaign.workspace_id,
            to_email=lead.email,
            subject=subject,
            body=body,
        )

        sent_email = SentEmail(
            lead_id=lead.id,
            campaign_id=campaign.id,
            email_account_id=send_result.email_account_id,
            message_id=send_result.message_id,
            thread_id=send_result.thread_id,
            email_subject=subject,
            email_body=body,
            status="SENT",
        )
        db.add(sent_email)
        db.flush()
        try:
            sync_sent_email_memory(db, campaign.workspace_id, sent_email)
        except MemoryServiceError:
            pass
        record_activity_log(
            db,
            workspace_id=campaign.workspace_id,
            lead_id=lead.id,
            campaign_id=campaign.id,
            event_type=EVENT_EMAIL_SENT,
            message=f"Sent scheduled email to {lead.email} for campaign {campaign.name}.",
            metadata={
                "sent_email_id": sent_email.id,
                "scheduled_email_id": scheduled_email.id,
                "message_id": sent_email.message_id,
                "subject": sent_email.email_subject,
                "delivery_mode": "scheduled",
                "step_number": scheduled_email.step_number,
            },
        )
        scheduled_email.status = "SENT"
        db.commit()

        return {"status": "sent", "message_id": send_result.message_id}
    except GmailSendServiceError as exc:
        if scheduled_email and exc.status_code >= 500 and self.request.retries < self.max_retries:
            scheduled_email.status = "QUEUED"
            db.commit()
            countdown = min(60 * (2 ** self.request.retries), 300)
            raise self.retry(exc=exc, countdown=countdown)
        if scheduled_email:
            scheduled_email.status = "FAILED"
            if campaign:
                notify_system_error(
                    db,
                    workspace_id=campaign.workspace_id,
                    title="Scheduled email send failed",
                    body=(
                        f"Sending step {scheduled_email.step_number} for campaign "
                        f"{campaign.name} to {lead.email if lead else 'the lead'} failed."
                    ),
                    metadata={
                        "scheduled_email_id": scheduled_email.id,
                        "campaign_id": campaign.id,
                        "lead_id": lead.id if lead else None,
                        "step_number": scheduled_email.step_number,
                        "error": str(exc),
                    },
                    resource_type="scheduled_email",
                    resource_id=scheduled_email.id,
                )
            db.commit()
        return {"status": "failed", "error": str(exc)}
    except Retry:
        raise
    except Exception as exc:
        if scheduled_email and self.request.retries < self.max_retries:
            scheduled_email.status = "QUEUED"
            db.commit()
            countdown = min(60 * (2 ** self.request.retries), 300)
            raise self.retry(exc=exc, countdown=countdown)
        if scheduled_email:
            scheduled_email.status = "FAILED"
            if campaign:
                notify_system_error(
                    db,
                    workspace_id=campaign.workspace_id,
                    title="Scheduled email processing failed",
                    body=(
                        f"Processing step {scheduled_email.step_number} for campaign "
                        f"{campaign.name} encountered an error."
                    ),
                    metadata={
                        "scheduled_email_id": scheduled_email.id,
                        "campaign_id": campaign.id,
                        "lead_id": lead.id if lead else None,
                        "step_number": scheduled_email.step_number,
                        "error": str(exc),
                    },
                    resource_type="scheduled_email",
                    resource_id=scheduled_email.id,
                )
            db.commit()
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()
