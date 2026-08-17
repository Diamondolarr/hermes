import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.onboarding import CompanyProfile, IdealCustomerProfile
from app.models.user import User
from app.models.user_setting import UserSetting
from app.models.workspace import Workspace
from app.utils.security import hash_password


def ensure_demo_user(db: Session) -> None:
    if not settings.demo_user_enabled:
        return

    email = settings.demo_user_email.strip().lower()
    password = settings.demo_user_password
    if not email or len(password) < 8:
        raise RuntimeError(
            "DEMO_USER_EMAIL and DEMO_USER_PASSWORD must be configured when demo user seeding is enabled."
        )

    user = db.query(User).filter(User.email == email).first()
    if user:
        user.name = settings.demo_user_name
        user.password_hash = hash_password(password)
        user.is_verified = True
        workspace = (
            db.query(Workspace).filter(Workspace.id == user.workspace_id).first()
        )
        if not workspace:
            workspace = Workspace(id=user.workspace_id, user_id=user.id)
            db.add(workspace)
    else:
        user_id = str(uuid.uuid4())
        workspace_id = str(uuid.uuid4())
        workspace = Workspace(
            id=workspace_id,
            user_id=user_id,
            onboarding_completed=True,
            human_approval_enabled=True,
        )
        user = User(
            id=user_id,
            name=settings.demo_user_name,
            email=email,
            password_hash=hash_password(password),
            workspace_id=workspace_id,
            is_verified=True,
        )
        db.add(workspace)
        db.add(user)

    workspace.onboarding_completed = True
    workspace.human_approval_enabled = True

    company_profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.workspace_id == workspace.id)
        .first()
    )
    if company_profile:
        company_profile.company_name = "Hermes Demo Co"
        company_profile.company_website = "https://hermes-demo.example"
        company_profile.product_description = (
            "AI SDR workspace for lead research, campaign planning, approvals, and reply workflows."
        )
        company_profile.industry = "B2B SaaS"
        company_profile.target_market = "Revenue teams at growing software companies"
    else:
        db.add(
            CompanyProfile(
                workspace_id=workspace.id,
                company_name="Hermes Demo Co",
                company_website="https://hermes-demo.example",
                product_description=(
                    "AI SDR workspace for lead research, campaign planning, approvals, and reply workflows."
                ),
                industry="B2B SaaS",
                target_market="Revenue teams at growing software companies",
            )
        )

    ideal_profile = (
        db.query(IdealCustomerProfile)
        .filter(IdealCustomerProfile.workspace_id == workspace.id)
        .first()
    )
    if ideal_profile:
        ideal_profile.target_industry = "B2B SaaS"
        ideal_profile.target_company_size = "11-50 employees"
        ideal_profile.target_roles = [
            "VP Sales",
            "Head of Growth",
            "Revenue Operations",
        ]
        ideal_profile.target_region = "North America"
        ideal_profile.pain_points = [
            "Low outbound reply rates",
            "Manual lead research",
            "Slow campaign approval cycles",
        ]
    else:
        db.add(
            IdealCustomerProfile(
                workspace_id=workspace.id,
                target_industry="B2B SaaS",
                target_company_size="11-50 employees",
                target_roles=[
                    "VP Sales",
                    "Head of Growth",
                    "Revenue Operations",
                ],
                target_region="North America",
                pain_points=[
                    "Low outbound reply rates",
                    "Manual lead research",
                    "Slow campaign approval cycles",
                ],
            )
        )

    user_setting = db.query(UserSetting).filter(UserSetting.user_id == user.id).first()
    if not user_setting:
        db.add(UserSetting(user_id=user.id))

    db.commit()
