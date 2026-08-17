from datetime import datetime

from jose import jwt

from app.core.config import settings


def create_access_token(
    subject: str, jti: str, expires_at: datetime, workspace_id: str
) -> str:
    payload = {
        "sub": subject,
        "jti": jti,
        "exp": expires_at,
        "typ": "access",
        "workspace_id": workspace_id,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
