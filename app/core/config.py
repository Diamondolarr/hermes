from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/aisdr"
    )
    jwt_secret_key: str = Field(default="change-me")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    rate_limiting_enabled: bool = Field(default=True)
    rate_limit_redis_url: str = Field(default="redis://localhost:6379/2")
    cache_redis_url: str = Field(default="redis://localhost:6379/3")
    admin_overview_cache_ttl_seconds: int = Field(default=60)
    admin_usage_cache_ttl_seconds: int = Field(default=120)
    campaign_analytics_cache_ttl_seconds: int = Field(default=120)
    verify_token_expire_hours: int = Field(default=24)
    reset_token_expire_hours: int = Field(default=1)
    app_base_url: str = Field(default="http://localhost:8000")
    frontend_app_url: str = Field(default="http://localhost:3000")
    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000"
    )
    encryption_key: str = Field(default="")
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/email/gmail/callback"
    )
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/1")
    celery_timezone: str = Field(default="UTC")
    celery_queue_default: str = Field(default="default")
    celery_queue_email_sending: str = Field(default="email_sending")
    celery_queue_reply_polling: str = Field(default="reply_polling")
    celery_queue_automation: str = Field(default="automation")
    celery_queue_ai_generation: str = Field(default="ai_generation")
    celery_queue_monitoring: str = Field(default="monitoring")
    celery_task_time_limit_seconds: int = Field(default=300)
    celery_task_soft_time_limit_seconds: int = Field(default=270)
    celery_result_expires_seconds: int = Field(default=3600)
    calendly_scheduling_link: str = Field(default="")
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-1.5-flash")
    gemini_analytics_model: str = Field(default="gemini-2.5-flash")
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-sonnet-4-20250514")
    demo_user_enabled: bool = Field(default=False)
    demo_user_email: str = Field(default="")
    demo_user_password: str = Field(default="")
    demo_user_name: str = Field(default="Demo User")

    @property
    def parsed_cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
