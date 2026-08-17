from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_reply import EmailReply
from app.models.reply_classification import ReplyClassification
from app.services.admin_monitoring import record_api_usage

ReplyCategory = Literal[
    "INTERESTED",
    "NOT_INTERESTED",
    "REQUEST_INFO",
    "REFERRAL",
    "UNSUBSCRIBE",
    "OTHER",
]


class ReplyClassificationServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ReplyClassificationPayload(BaseModel):
    category: ReplyCategory
    confidence_score: float
    reason: str


def _build_prompt(reply_body: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Classify inbound sales email replies into one of these categories: "
                "INTERESTED, NOT_INTERESTED, REQUEST_INFO, REFERRAL, UNSUBSCRIBE, OTHER. "
                "Return a structured response only. "
                "Use INTERESTED for clear positive buying intent. "
                "Use NOT_INTERESTED for explicit rejection without asking to stop future contact. "
                "Use REQUEST_INFO when the sender asks for more details, pricing, deck, documentation, or next-step information. "
                "Use REFERRAL when the sender directs the conversation to another person or team. "
                "Use UNSUBSCRIBE when the sender asks not to be contacted again or to be removed from future outreach. "
                "Use OTHER when none of the above clearly apply."
            ),
        },
        {
            "role": "user",
            "content": f"Reply text:\n{reply_body.strip()}",
        },
    ]


def classify_reply_text(reply_body: str) -> ReplyClassificationPayload:
    body = reply_body.strip()
    if not body:
        raise ReplyClassificationServiceError(
            "Reply text is required for classification.", status_code=400
        )
    if not settings.openai_api_key:
        raise ReplyClassificationServiceError(
            "OPENAI_API_KEY is not configured.", status_code=500
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ReplyClassificationServiceError(
            "OpenAI SDK is not installed. Run `pip install -r requirements.txt`.",
            status_code=500,
        ) from exc

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.responses.parse(
            model=settings.openai_model,
            input=_build_prompt(body),
            text_format=ReplyClassificationPayload,
        )
    except Exception as exc:
        raise ReplyClassificationServiceError(
            f"OpenAI request failed for model `{settings.openai_model}`: {exc}",
            status_code=502,
        ) from exc

    payload = getattr(response, "output_parsed", None)
    if not payload:
        raise ReplyClassificationServiceError(
            "OpenAI did not return a structured reply classification.",
            status_code=502,
        )

    confidence = max(0.0, min(1.0, float(payload.confidence_score)))
    reason = payload.reason.strip()[:1000]
    if not reason:
        reason = "No explanation returned."

    return ReplyClassificationPayload(
        category=payload.category,
        confidence_score=confidence,
        reason=reason,
    )


def ensure_reply_classification(
    db: Session, email_reply: EmailReply
) -> ReplyClassification:
    classification = (
        db.query(ReplyClassification)
        .filter(ReplyClassification.email_reply_id == email_reply.id)
        .first()
    )
    if classification:
        return classification

    try:
        payload = classify_reply_text(email_reply.reply_body)
    except Exception:
        record_api_usage(
            db,
            workspace_id=email_reply.lead.workspace_id,
            provider="openai",
            feature="reply_classification",
            model_name=settings.openai_model,
            success=False,
            metadata={"lead_id": email_reply.lead_id, "reply_id": email_reply.id},
        )
        raise
    record_api_usage(
        db,
        workspace_id=email_reply.lead.workspace_id,
        provider="openai",
        feature="reply_classification",
        model_name=settings.openai_model,
        success=True,
        metadata={"lead_id": email_reply.lead_id, "reply_id": email_reply.id},
    )
    classification = ReplyClassification(
        email_reply_id=email_reply.id,
        lead_id=email_reply.lead_id,
        category=payload.category,
        confidence_score=payload.confidence_score,
        reason=payload.reason,
    )
    db.add(classification)
    db.flush()
    return classification
