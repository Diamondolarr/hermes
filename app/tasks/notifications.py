from app.db.session import SessionLocal
from app.services.notifications import (
    emit_booked_meeting_notifications,
    emit_campaign_finished_notifications,
)
from app.tasks.celery_app import celery_app


@celery_app.task(
    name="app.tasks.sync_notifications",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def sync_notifications() -> dict[str, int]:
    db = SessionLocal()
    try:
        booked_meetings = emit_booked_meeting_notifications(db)
        finished_campaigns = emit_campaign_finished_notifications(db)
        db.commit()
        return {
            "booked_meetings": booked_meetings,
            "finished_campaigns": finished_campaigns,
        }
    finally:
        db.close()
