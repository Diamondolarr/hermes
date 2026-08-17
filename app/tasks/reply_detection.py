from app.db.session import SessionLocal
from app.models.email import EmailAccount
from app.services.gmail_reply_detection import (
    ReplyDetectionServiceError,
    poll_gmail_replies_for_account,
)
from app.services.notifications import notify_system_error
from app.tasks.celery_app import celery_app


@celery_app.task(
    name="app.tasks.poll_gmail_replies",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def poll_gmail_replies() -> dict[str, int]:
    db = SessionLocal()
    try:
        accounts = (
            db.query(EmailAccount)
            .filter(EmailAccount.provider == "gmail")
            .order_by(EmailAccount.connected_at.asc())
            .all()
        )

        processed_accounts = 0
        stored_replies = 0
        memories_indexed = 0
        memory_failures = 0
        classified_replies = 0
        classification_failures = 0
        meetings_created = 0
        meeting_failures = 0
        generated_replies = 0
        generation_failures = 0
        notification_failures = 0
        for account in accounts:
            try:
                result = poll_gmail_replies_for_account(db, account)
            except ReplyDetectionServiceError as exc:
                db.rollback()
                notify_system_error(
                    db,
                    workspace_id=account.workspace_id,
                    title="Reply polling failed",
                    body=(
                        f"Could not poll replies for Gmail account {account.email_address}."
                    ),
                    metadata={
                        "email_account_id": account.id,
                        "provider": account.provider,
                        "error": str(exc),
                    },
                    resource_type="email_account",
                    resource_id=account.id,
                )
                db.commit()
                notification_failures += 1
                continue

            stored_replies += result["stored"]
            memories_indexed += result["memories_indexed"]
            memory_failures += result["memory_failures"]
            classified_replies += result["classified"]
            classification_failures += result["classification_failed"]
            meetings_created += result["meetings_created"]
            meeting_failures += result["meeting_failures"]
            generated_replies += result["generated"]
            generation_failures += result["generation_failed"]
            processed_accounts += 1
            db.commit()

        return {
            "accounts": processed_accounts,
            "stored_replies": stored_replies,
            "memories_indexed": memories_indexed,
            "memory_failures": memory_failures,
            "classified_replies": classified_replies,
            "classification_failures": classification_failures,
            "meetings_created": meetings_created,
            "meeting_failures": meeting_failures,
            "generated_replies": generated_replies,
            "generation_failures": generation_failures,
            "notification_failures": notification_failures,
        }
    finally:
        db.close()
