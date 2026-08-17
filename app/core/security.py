from cryptography.fernet import Fernet

from app.core.config import settings


def validate_security_configuration() -> None:
    jwt_secret = settings.jwt_secret_key.strip()
    if not jwt_secret or jwt_secret == "change-me" or len(jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a strong value of at least 32 characters."
        )

    if settings.encryption_key:
        try:
            Fernet(settings.encryption_key.encode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                "ENCRYPTION_KEY must be a valid Fernet key."
            ) from exc

    if (
        settings.google_client_id.strip() or settings.google_client_secret.strip()
    ) and not settings.encryption_key.strip():
        raise RuntimeError(
            "ENCRYPTION_KEY must be configured when Gmail OAuth is enabled."
        )

    if settings.rate_limiting_enabled and not settings.rate_limit_redis_url.strip():
        raise RuntimeError(
            "RATE_LIMIT_REDIS_URL must be configured when rate limiting is enabled."
        )
