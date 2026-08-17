from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.automation_rule import AutomationRule
from app.models.campaign import Campaign
from app.schemas.automation_rules import (
    AutomationRuleCreateRequest,
    AutomationRuleResponse,
)
from app.utils.auth import get_current_user

router = APIRouter()


@router.post("", response_model=AutomationRuleResponse, status_code=status.HTTP_201_CREATED)
def create_automation_rule(
    payload: AutomationRuleCreateRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AutomationRuleResponse:
    _, workspace = current

    if payload.campaign_id:
        campaign = (
            db.query(Campaign)
            .filter(
                Campaign.id == payload.campaign_id,
                Campaign.workspace_id == workspace.id,
            )
            .first()
        )
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found.")

    rule = AutomationRule(
        workspace_id=workspace.id,
        campaign_id=payload.campaign_id,
        name=payload.name.strip(),
        trigger_type=payload.trigger_type,
        delay_days=payload.delay_days,
        action_type=payload.action_type,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return AutomationRuleResponse(
        id=rule.id,
        workspace_id=rule.workspace_id,
        campaign_id=rule.campaign_id,
        name=rule.name,
        trigger_type=rule.trigger_type,
        delay_days=rule.delay_days,
        action_type=rule.action_type,
        is_active=rule.is_active,
        created_at=rule.created_at,
    )


@router.get("", response_model=list[AutomationRuleResponse])
def list_automation_rules(
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AutomationRuleResponse]:
    _, workspace = current

    rules = (
        db.query(AutomationRule)
        .filter(AutomationRule.workspace_id == workspace.id)
        .order_by(AutomationRule.created_at.asc())
        .all()
    )

    return [
        AutomationRuleResponse(
            id=rule.id,
            workspace_id=rule.workspace_id,
            campaign_id=rule.campaign_id,
            name=rule.name,
            trigger_type=rule.trigger_type,
            delay_days=rule.delay_days,
            action_type=rule.action_type,
            is_active=rule.is_active,
            created_at=rule.created_at,
        )
        for rule in rules
    ]
