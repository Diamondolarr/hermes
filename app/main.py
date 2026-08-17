from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.security import validate_security_configuration
from app.db.base import Base
from app.db.bootstrap import ensure_database_extensions, ensure_schema_extensions
from app.db.demo import ensure_demo_user
from app.db.session import engine
from app.db.session import SessionLocal
from app.routers.activity_logs import router as activity_logs_router
from app.routers.admin import router as admin_router
from app.routers.approvals import router as approvals_router
from app.routers.automation_rules import router as automation_rules_router
from app.routers.auth import router as auth_router
from app.routers.campaigns import router as campaigns_router
from app.routers.companies import router as companies_router
from app.routers.dashboard import router as dashboard_router
from app.routers.email import router as email_router
from app.routers.followups import router as followups_router
from app.routers.generated_emails import router as generated_emails_router
from app.routers.health import router as health_router
from app.routers.lead_insights import router as lead_insights_router
from app.routers.leads import router as leads_router
from app.routers.memory import router as memory_router
from app.routers.notifications import router as notifications_router
from app.routers.onboarding import router as onboarding_router
from app.routers.sales_insights import router as sales_insights_router
from app.routers.user_settings import router as user_settings_router
import app.models  # noqa: F401

from app.utils.rate_limit import rate_limit_callback, rate_limit_identifier


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_security_configuration()
    ensure_database_extensions(engine)
    Base.metadata.create_all(bind=engine)
    ensure_schema_extensions(engine)
    db = SessionLocal()
    try:
        ensure_demo_user(db)
    finally:
        db.close()
    if settings.rate_limiting_enabled:
        try:
            redis_client = redis.from_url(
                settings.rate_limit_redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await FastAPILimiter.init(
                redis_client,
                prefix="aisdr-rate-limit",
                identifier=rate_limit_identifier,
                http_callback=rate_limit_callback,
            )
        except Exception as exc:
            raise RuntimeError(
                "Failed to initialize Redis-backed rate limiting. "
                "Check RATE_LIMIT_REDIS_URL and ensure Redis is running."
            ) from exc

    try:
        yield
    finally:
        if settings.rate_limiting_enabled:
            await FastAPILimiter.close()


app = FastAPI(title="AI SDR API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(activity_logs_router, prefix="/activity-logs", tags=["activity-logs"])
app.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
app.include_router(
    automation_rules_router, prefix="/automation-rules", tags=["automation-rules"]
)
app.include_router(campaigns_router, prefix="/campaigns", tags=["campaigns"])
app.include_router(companies_router, prefix="/companies", tags=["companies"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
app.include_router(email_router, prefix="/email", tags=["email"])
app.include_router(followups_router, prefix="/followups", tags=["followups"])
app.include_router(
    generated_emails_router,
    prefix="/generated-emails",
    tags=["generated-emails"],
)
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(lead_insights_router, prefix="/lead-insights", tags=["lead-insights"])
app.include_router(leads_router, prefix="/leads", tags=["leads"])
app.include_router(memory_router, prefix="/memory", tags=["memory"])
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
app.include_router(onboarding_router, prefix="/onboarding", tags=["onboarding"])
app.include_router(
    sales_insights_router, prefix="/sales-insights", tags=["sales-insights"]
)
app.include_router(user_settings_router, prefix="/user-settings", tags=["user-settings"])
