from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_database_extensions(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return

    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as exc:
        raise RuntimeError(
            "Failed to enable the PostgreSQL `vector` extension. "
            "Install pgvector on your PostgreSQL server, then restart the API."
        ) from exc


def ensure_schema_extensions(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "leads" in table_names:
        lead_columns = {column["name"] for column in inspector.get_columns("leads")}
        if "company_id" not in lead_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE leads ADD COLUMN company_id VARCHAR(36)")
                )

    if "campaigns" in table_names:
        campaign_columns = {
            column["name"] for column in inspector.get_columns("campaigns")
        }
        missing_statements = []
        if "daily_send_limit" not in campaign_columns:
            missing_statements.append(
                "ALTER TABLE campaigns ADD COLUMN daily_send_limit INTEGER NOT NULL DEFAULT 50"
            )
        if "send_time_window_start" not in campaign_columns:
            missing_statements.append(
                "ALTER TABLE campaigns ADD COLUMN send_time_window_start VARCHAR(5) NOT NULL DEFAULT '09:00'"
            )
        if "send_time_window_end" not in campaign_columns:
            missing_statements.append(
                "ALTER TABLE campaigns ADD COLUMN send_time_window_end VARCHAR(5) NOT NULL DEFAULT '17:00'"
            )
        if "send_timezone" not in campaign_columns:
            missing_statements.append(
                "ALTER TABLE campaigns ADD COLUMN send_timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'"
            )
        if "followup_delay_days" not in campaign_columns:
            missing_statements.append(
                "ALTER TABLE campaigns ADD COLUMN followup_delay_days INTEGER NOT NULL DEFAULT 3"
            )
        if missing_statements:
            with engine.begin() as connection:
                for statement in missing_statements:
                    connection.execute(text(statement))

    if "sent_emails" in table_names:
        sent_email_columns = {
            column["name"] for column in inspector.get_columns("sent_emails")
        }
        sent_email_statements = []
        if "email_account_id" not in sent_email_columns:
            sent_email_statements.append(
                "ALTER TABLE sent_emails ADD COLUMN email_account_id VARCHAR(36)"
            )
        if "thread_id" not in sent_email_columns:
            sent_email_statements.append(
                "ALTER TABLE sent_emails ADD COLUMN thread_id VARCHAR(255)"
            )
        if "email_subject" not in sent_email_columns:
            sent_email_statements.append(
                "ALTER TABLE sent_emails ADD COLUMN email_subject VARCHAR(255)"
            )
        if "email_body" not in sent_email_columns:
            sent_email_statements.append(
                "ALTER TABLE sent_emails ADD COLUMN email_body VARCHAR(5000)"
            )
        if sent_email_statements:
            with engine.begin() as connection:
                for statement in sent_email_statements:
                    connection.execute(text(statement))

    if "workspaces" in table_names:
        workspace_columns = {
            column["name"] for column in inspector.get_columns("workspaces")
        }
        if "human_approval_enabled" not in workspace_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE workspaces ADD COLUMN human_approval_enabled BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )

    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_admin" not in user_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )

    if "scheduled_emails" in table_names:
        scheduled_email_columns = {
            column["name"] for column in inspector.get_columns("scheduled_emails")
        }
        scheduled_email_statements = []
        if "draft_subject" not in scheduled_email_columns:
            scheduled_email_statements.append(
                "ALTER TABLE scheduled_emails ADD COLUMN draft_subject VARCHAR(255)"
            )
        if "draft_body" not in scheduled_email_columns:
            scheduled_email_statements.append(
                "ALTER TABLE scheduled_emails ADD COLUMN draft_body VARCHAR(5000)"
            )
        if "approval_status" not in scheduled_email_columns:
            scheduled_email_statements.append(
                "ALTER TABLE scheduled_emails ADD COLUMN approval_status VARCHAR(50) NOT NULL DEFAULT 'APPROVED'"
            )
        if "approved_by_user_id" not in scheduled_email_columns:
            scheduled_email_statements.append(
                "ALTER TABLE scheduled_emails ADD COLUMN approved_by_user_id VARCHAR(36)"
            )
        if "approved_at" not in scheduled_email_columns:
            scheduled_email_statements.append(
                "ALTER TABLE scheduled_emails ADD COLUMN approved_at TIMESTAMP"
            )
        if "rejected_by_user_id" not in scheduled_email_columns:
            scheduled_email_statements.append(
                "ALTER TABLE scheduled_emails ADD COLUMN rejected_by_user_id VARCHAR(36)"
            )
        if "rejected_at" not in scheduled_email_columns:
            scheduled_email_statements.append(
                "ALTER TABLE scheduled_emails ADD COLUMN rejected_at TIMESTAMP"
            )
        if "rejection_reason" not in scheduled_email_columns:
            scheduled_email_statements.append(
                "ALTER TABLE scheduled_emails ADD COLUMN rejection_reason VARCHAR(1000)"
            )
        if scheduled_email_statements:
            with engine.begin() as connection:
                for statement in scheduled_email_statements:
                    connection.execute(text(statement))
