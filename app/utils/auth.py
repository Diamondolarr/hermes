from datetime import datetime
from typing import Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.demo import is_demo_identity
from app.db.session import get_db
from app.models.token import UserSession
from app.models.user import User
from app.models.workspace import Workspace

_security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    db: Session = Depends(get_db),
) -> Tuple[User, Workspace]:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")
    token_type = payload.get("typ")
    workspace_id = payload.get("workspace_id")
    if not user_id or not jti or token_type != "access" or not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    session = (
        db.query(UserSession)
        .filter(
            UserSession.jti == jti,
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if (
        (not session or session.expires_at < datetime.utcnow())
        and not is_demo_identity(user_id, workspace_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    return user, workspace


def get_current_admin(
    current: Tuple[User, Workspace] = Depends(get_current_user),
) -> Tuple[User, Workspace]:
    user, workspace = current
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user, workspace
