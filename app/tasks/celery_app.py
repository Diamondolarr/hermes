from celery import Celery
from kombu import Queue

from app.core.config import settings


celery_app = Celery(
    "aisdr",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    timezone=settings.celery_timezone,
    enable_utc=True,
    task_default_queue=settings.celery_queue_default,
    task_queues=(
        Queue(settings.celery_queue_default),
        Queue(settings.celery_queue_email_sending),
        Queue(settings.celery_queue_reply_polling),
        Queue(settings.celery_queue_automation),
        Queue(settings.celery_queue_ai_generation),
        Queue(settings.celery_queue_monitoring),
    ),
    task_routes={
        "app.tasks.dispatch_due_scheduled_emails": {
            "queue": settings.celery_queue_email_sending
        },
        "app.tasks.send_scheduled_email": {
            "queue": settings.celery_queue_email_sending
        },
        "app.tasks.poll_gmail_replies": {
            "queue": settings.celery_queue_reply_polling
        },
        "app.tasks.evaluate_automation_rules": {
            "queue": settings.celery_queue_automation
        },
        "app.tasks.sync_notifications": {
            "queue": settings.celery_queue_monitoring
        },
        "app.tasks.sync_abuse_alerts": {
            "queue": settings.celery_queue_monitoring
        },
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_time_limit=settings.celery_task_time_limit_seconds,
    task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
    result_expires=settings.celery_result_expires_seconds,
    imports=(
        "app.tasks.admin_monitoring",
        "app.tasks.automation",
        "app.tasks.email_scheduling",
        "app.tasks.notifications",
        "app.tasks.reply_detection",
    ),
    beat_schedule={
        "dispatch-due-scheduled-emails": {
            "task": "app.tasks.dispatch_due_scheduled_emails",
            "schedule": 300.0,
        },
        "sync-abuse-alerts": {
            "task": "app.tasks.sync_abuse_alerts",
            "schedule": 300.0,
        },
        "poll-gmail-replies": {
            "task": "app.tasks.poll_gmail_replies",
            "schedule": 300.0,
        },
        "sync-notifications": {
            "task": "app.tasks.sync_notifications",
            "schedule": 300.0,
        },
        "evaluate-automation-rules": {
            "task": "app.tasks.evaluate_automation_rules",
            "schedule": 300.0,
        },
    },
)
