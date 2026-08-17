from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.automation_rule import AutomationRule, AutomationRuleExecution
from app.models.campaign import Campaign
from app.models.email_reply import EmailReply
from app.models.followup import Followup
from app.models.lead import Lead
from app.models.scheduled_email import ScheduledEmail
from app.models.sent_email import SentEmail
from app.services.email_scheduling import (
    ACTIVE_SCHEDULE_STATUSES,
    FOLLOWUP_EMAIL_TYPE,
    default_approval_status,
    ensure_followups,
    resolve_next_send_time,
)
from app.services.followup_generation import FollowupGenerationServiceError
from app.services.lead_research import LeadResearchServiceError
from app.services.notifications import notify_system_error
from app.services.sales_insight import SalesInsightServiceError


@dataclass
class AutomationEvaluationResult:
    rules_evaluated: int = 0
    leads_considered: int = 0
    actions_scheduled: int = 0
    skipped_existing_schedule: int = 0
    skipped_due_to_reply: int = 0
    skipped_no_followup_available: int = 0
    execution_failures: int = 0


def _get_scoped_campaigns(db: Session, rule: AutomationRule) -> list[Campaign]:
    query = db.query(Campaign).filter(Campaign.workspace_id == rule.workspace_id)
    if rule.campaign_id:
        query = query.filter(Campaign.id == rule.campaign_id)
    return query.all()


def _get_last_sent_emails(db: Session, campaign_id: str) -> list[SentEmail]:
    sent_rows = (
        db.query(SentEmail)
        .filter(SentEmail.campaign_id == campaign_id, SentEmail.status == "SENT")
        .order_by(SentEmail.lead_id.asc(), SentEmail.sent_at.desc())
        .all()
    )

    latest_by_lead: dict[str, SentEmail] = {}
    for row in sent_rows:
        if row.lead_id not in latest_by_lead:
            latest_by_lead[row.lead_id] = row
    return list(latest_by_lead.values())


def _has_reply_after_last_send(db: Session, last_sent: SentEmail) -> bool:
    query = db.query(EmailReply).filter(
        EmailReply.lead_id == last_sent.lead_id,
        EmailReply.received_at > last_sent.sent_at,
    )
    if last_sent.thread_id:
        query = query.filter(EmailReply.thread_id == last_sent.thread_id)
        if last_sent.email_account_id:
            query = query.filter(
                EmailReply.email_account_id == last_sent.email_account_id
            )
    return query.first() is not None


def _next_followup_step(db: Session, lead_id: str, campaign_id: str) -> int | None:
    scheduled_items = (
        db.query(ScheduledEmail)
        .filter(
            ScheduledEmail.lead_id == lead_id,
            ScheduledEmail.campaign_id == campaign_id,
        )
        .all()
    )

    sent_steps = {item.step_number for item in scheduled_items if item.status == "SENT"}
    existing_active_steps = {
        item.step_number
        for item in scheduled_items
        if item.status in ACTIVE_SCHEDULE_STATUSES
    }

    has_any_sent_email = (
        db.query(SentEmail.id)
        .filter(SentEmail.lead_id == lead_id, SentEmail.campaign_id == campaign_id)
        .first()
        is not None
    )

    highest_sent_step = max(sent_steps) if sent_steps else (0 if has_any_sent_email else -1)
    next_step = highest_sent_step + 1
    if next_step < 1 or next_step > 4:
        return None
    if next_step in existing_active_steps:
        return -1
    return next_step


def _record_execution(
    db: Session,
    *,
    rule: AutomationRule,
    lead_id: str,
    campaign_id: str,
    target_step_number: int,
    status: str,
) -> None:
    execution = AutomationRuleExecution(
        rule_id=rule.id,
        lead_id=lead_id,
        campaign_id=campaign_id,
        target_step_number=target_step_number,
        status=status,
    )
    db.add(execution)
    db.flush()


def evaluate_automation_rules(db: Session) -> AutomationEvaluationResult:
    now = datetime.utcnow()
    result = AutomationEvaluationResult()

    active_rules = (
        db.query(AutomationRule)
        .filter(AutomationRule.is_active.is_(True))
        .order_by(AutomationRule.created_at.asc())
        .all()
    )
    result.rules_evaluated = len(active_rules)

    for rule in active_rules:
        campaigns = _get_scoped_campaigns(db, rule)
        for campaign in campaigns:
            latest_sent_rows = _get_last_sent_emails(db, campaign.id)
            for last_sent in latest_sent_rows:
                result.leads_considered += 1
                if last_sent.sent_at > now - timedelta(days=rule.delay_days):
                    continue

                if _has_reply_after_last_send(db, last_sent):
                    result.skipped_due_to_reply += 1
                    continue

                next_step = _next_followup_step(db, last_sent.lead_id, campaign.id)
                if next_step == -1:
                    result.skipped_existing_schedule += 1
                    continue
                if next_step is None:
                    result.skipped_no_followup_available += 1
                    continue

                existing_execution = (
                    db.query(AutomationRuleExecution)
                    .filter(
                        AutomationRuleExecution.rule_id == rule.id,
                        AutomationRuleExecution.lead_id == last_sent.lead_id,
                        AutomationRuleExecution.campaign_id == campaign.id,
                        AutomationRuleExecution.target_step_number == next_step,
                    )
                    .first()
                )
                if existing_execution:
                    result.skipped_existing_schedule += 1
                    continue

                lead = (
                    db.query(Lead)
                    .filter(
                        Lead.id == last_sent.lead_id,
                        Lead.workspace_id == rule.workspace_id,
                    )
                    .first()
                )
                if not lead:
                    result.execution_failures += 1
                    continue

                try:
                    with db.begin_nested():
                        followups = ensure_followups(
                            db,
                            rule.workspace_id,
                            lead,
                            campaign,
                            start_date=last_sent.sent_at,
                            regenerate=False,
                        )
                        followup_map: dict[int, Followup] = {
                            item.step_number: item for item in followups
                        }
                        followup = followup_map.get(next_step)
                        if not followup:
                            result.skipped_no_followup_available += 1
                            continue

                        scheduled_for = resolve_next_send_time(
                            db,
                            campaign,
                            earliest_time=max(now, followup.scheduled_date),
                        )
                        followup.scheduled_date = scheduled_for

                        item = (
                            db.query(ScheduledEmail)
                            .filter(
                                ScheduledEmail.lead_id == lead.id,
                                ScheduledEmail.campaign_id == campaign.id,
                                ScheduledEmail.step_number == next_step,
                            )
                            .first()
                        )
                        if item:
                            item.email_type = FOLLOWUP_EMAIL_TYPE
                            item.draft_subject = followup.email_subject
                            item.draft_body = followup.email_body
                            item.scheduled_for = scheduled_for
                            item.status = "PENDING"
                            item.approval_status = default_approval_status(
                                rule.workspace.human_approval_enabled
                            )
                            item.approved_by_user_id = None
                            item.approved_at = None
                            item.rejected_by_user_id = None
                            item.rejected_at = None
                            item.rejection_reason = None
                        else:
                            item = ScheduledEmail(
                                lead_id=lead.id,
                                campaign_id=campaign.id,
                                step_number=next_step,
                                email_type=FOLLOWUP_EMAIL_TYPE,
                                draft_subject=followup.email_subject,
                                draft_body=followup.email_body,
                                scheduled_for=scheduled_for,
                                status="PENDING",
                                approval_status=default_approval_status(
                                    rule.workspace.human_approval_enabled
                                ),
                            )
                            db.add(item)
                        db.flush()
                        _record_execution(
                            db,
                            rule=rule,
                            lead_id=lead.id,
                            campaign_id=campaign.id,
                            target_step_number=next_step,
                            status="SCHEDULED",
                        )
                        campaign.status = "SCHEDULED"

                    result.actions_scheduled += 1
                except (
                    FollowupGenerationServiceError,
                    LeadResearchServiceError,
                    SalesInsightServiceError,
                ) as exc:
                    notify_system_error(
                        db,
                        workspace_id=rule.workspace_id,
                        title="Automation rule execution failed",
                        body=(
                            f"Rule {rule.name} could not schedule follow-up step "
                            f"{next_step} for {lead.email} in campaign {campaign.name}."
                        ),
                        metadata={
                            "rule_id": rule.id,
                            "campaign_id": campaign.id,
                            "lead_id": lead.id,
                            "target_step_number": next_step,
                            "error": str(exc),
                        },
                        resource_type="automation_rule_execution",
                        resource_id=f"{rule.id}:{lead.id}:{campaign.id}:{next_step}",
                    )
                    result.execution_failures += 1

    return result
