from app.db.session import SessionLocal
from app.schemas.automation_rules import AutomationRuleExecutionSummary
from app.services.automation import evaluate_automation_rules
from app.tasks.celery_app import celery_app


@celery_app.task(
    name="app.tasks.evaluate_automation_rules",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def evaluate_automation_rules_task() -> dict[str, int]:
    db = SessionLocal()
    try:
        result = evaluate_automation_rules(db)
        db.commit()
        summary = AutomationRuleExecutionSummary(
            rules_evaluated=result.rules_evaluated,
            leads_considered=result.leads_considered,
            actions_scheduled=result.actions_scheduled,
            skipped_existing_schedule=result.skipped_existing_schedule,
            skipped_due_to_reply=result.skipped_due_to_reply,
            skipped_no_followup_available=result.skipped_no_followup_available,
            execution_failures=result.execution_failures,
        )
        return summary.model_dump()
    finally:
        db.close()
