from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.cache import ping_redis

router = APIRouter()


def _database_ok() -> bool:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        db.close()


@router.get("/live")
def health_live() -> dict:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready")
def health_ready() -> dict:
    database_ok = _database_ok()
    broker_ok = ping_redis(settings.celery_broker_url)
    cache_ok = ping_redis(settings.cache_redis_url)
    rate_limit_ok = (
        ping_redis(settings.rate_limit_redis_url)
        if settings.rate_limiting_enabled
        else True
    )
    healthy = database_ok and broker_ok and cache_ok and rate_limit_ok
    return {
        "status": "ready" if healthy else "degraded",
        "database": database_ok,
        "broker_redis": broker_ok,
        "cache_redis": cache_ok,
        "rate_limit_redis": rate_limit_ok,
    }


@router.get("/infra")
def health_infra() -> dict:
    return {
        "status": "ok",
        "queues": {
            "default": settings.celery_queue_default,
            "email_sending": settings.celery_queue_email_sending,
            "reply_polling": settings.celery_queue_reply_polling,
            "automation": settings.celery_queue_automation,
            "ai_generation": settings.celery_queue_ai_generation,
            "monitoring": settings.celery_queue_monitoring,
        },
        "redis": {
            "broker": settings.celery_broker_url,
            "backend": settings.celery_result_backend,
            "cache": settings.cache_redis_url,
        },
        "celery": {
            "timezone": settings.celery_timezone,
            "task_time_limit_seconds": settings.celery_task_time_limit_seconds,
            "task_soft_time_limit_seconds": settings.celery_task_soft_time_limit_seconds,
        },
    }
