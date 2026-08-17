from app.db.session import SessionLocal
from app.services.admin_monitoring import sync_abuse_alerts
from app.tasks.celery_app import celery_app


@celery_app.task(
    name="app.tasks.sync_abuse_alerts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def sync_abuse_alerts_task() -> dict[str, int]:
    db = SessionLocal()
    try:
        alerts = sync_abuse_alerts(db)
        db.commit()
        return {
            "total_alerts": len(alerts),
            "open_alerts": sum(1 for alert in alerts if alert.status == "OPEN"),
            "resolved_alerts": sum(
                1 for alert in alerts if alert.status == "RESOLVED"
            ),
        }
    finally:
        db.close()
