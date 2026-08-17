import re
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_reply import EmailReply
from app.models.generated_reply import GeneratedReply
from app.models.onboarding import CompanyProfile
from app.models.reply_classification import ReplyClassification
from app.models.sent_email import SentEmail
from app.services.admin_monitoring import record_api_usage

_ALLOWED_REPLY_CATEGORIES = {"INTERESTED", "REQUEST_INFO", "REFERRAL"}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _trim_text(value: str, limit: int) -> str:
    return _clean_text(value)[:limit]


class ReplyGenerationServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ClaudeGeneratedReplyPayload(BaseModel):
    subject: str
    body: str
    reply_goal: str


@dataclass
class OutboundContext:
    subject: str | None
    body: str | None


def category_allows_generated_reply(category: str) -> bool:
    return category in _ALLOWED_REPLY_CATEGORIES


def _extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        raise ReplyGenerationServiceError(
            "Claude returned an empty reply generation response.", status_code=502
        )

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        return match.group(0)
    return text


def _extract_response_text(message) -> str:
    blocks = getattr(message, "content", []) or []
    parts = []
    for block in blocks:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _call_claude(prompt: str) -> ClaudeGeneratedReplyPayload:
    if not settings.anthropic_api_key:
        raise ReplyGenerationServiceError(
            "ANTHROPIC_API_KEY is not configured.", status_code=500
        )

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise ReplyGenerationServiceError(
            "Anthropic SDK is not installed. Run `pip install -r requirements.txt`.",
            status_code=500,
        ) from exc

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1000,
            temperature=0.4,
            system=(
                "You write concise, helpful B2B reply emails. "
                "Always return valid JSON only."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise ReplyGenerationServiceError(
            f"Claude request failed for model `{settings.anthropic_model}`: {exc}",
            status_code=502,
        ) from exc

    payload_text = _extract_json_payload(_extract_response_text(message))
    try:
        return ClaudeGeneratedReplyPayload.model_validate_json(payload_text)
    except ValidationError as exc:
        raise ReplyGenerationServiceError(
            "Claude returned an invalid JSON payload for reply generation.",
            status_code=502,
        ) from exc


def _latest_outbound_context(db: Session, email_reply: EmailReply) -> OutboundContext:
    sent_email = (
        db.query(SentEmail)
        .filter(
            SentEmail.lead_id == email_reply.lead_id,
            SentEmail.email_account_id == email_reply.email_account_id,
            SentEmail.thread_id == email_reply.thread_id,
            SentEmail.status == "SENT",
        )
        .order_by(SentEmail.sent_at.desc())
        .first()
    )
    if sent_email and (sent_email.email_subject or sent_email.email_body):
        return OutboundContext(
            subject=sent_email.email_subject,
            body=sent_email.email_body,
        )

    sent_email = (
        db.query(SentEmail)
        .filter(
            SentEmail.lead_id == email_reply.lead_id,
            SentEmail.email_account_id == email_reply.email_account_id,
            SentEmail.status == "SENT",
        )
        .order_by(SentEmail.sent_at.desc())
        .first()
    )
    if sent_email and (sent_email.email_subject or sent_email.email_body):
        return OutboundContext(
            subject=sent_email.email_subject,
            body=sent_email.email_body,
        )

    return OutboundContext(subject=None, body=None)


def _build_prompt(
    *,
    lead_name: str,
    lead_role: str,
    lead_company: str,
    company_name: str,
    product_description: str,
    company_industry: str,
    target_market: str,
    inbound_reply: str,
    reply_category: str,
    classification_reason: str,
    latest_outbound_subject: str | None,
    latest_outbound_body: str | None,
    meeting_link: str | None,
) -> str:
    return f"""
Write a suggested email reply to an inbound sales response.

Return exactly one JSON object with these keys:
- subject
- body
- reply_goal

Rules:
- Output valid JSON only.
- Do not include markdown or code fences.
- `reply_goal` must be one of: send_info, answer_question, propose_meeting.
- Subject must be under 80 characters.
- Body must be plain text, under 1200 characters, and sound natural and professional.
- Be helpful and specific, but do not invent product facts, pricing, case studies, or promises.
- If the prospect asked for more information, the reply should offer helpful next steps.
- If the reply indicates interest, default toward proposing a meeting.
- If the reply is a referral, acknowledge it briefly and adapt the response for the referred contact.
- If a meeting link is provided, include it naturally when proposing a meeting.

Lead:
- Name: {lead_name or "there"}
- Role: {lead_role}
- Company: {lead_company}

Our company profile:
- Company name: {company_name}
- Product description: {product_description}
- Industry: {company_industry}
- Target market: {target_market}

Latest outbound email subject: {latest_outbound_subject or "None"}
Latest outbound email body: {latest_outbound_body or "None"}

Inbound reply:
{inbound_reply}

Reply classification:
- Category: {reply_category}
- Reason: {classification_reason}

Meeting link to use if appropriate: {meeting_link or "None"}
""".strip()


def generate_reply(
    *,
    lead_name: str,
    lead_role: str,
    lead_company: str,
    company_name: str,
    product_description: str,
    company_industry: str,
    target_market: str,
    inbound_reply: str,
    reply_category: str,
    classification_reason: str,
    latest_outbound_subject: str | None,
    latest_outbound_body: str | None,
    meeting_link: str | None = None,
) -> ClaudeGeneratedReplyPayload:
    prompt = _build_prompt(
        lead_name=_trim_text(lead_name, 255),
        lead_role=_trim_text(lead_role, 255),
        lead_company=_trim_text(lead_company, 255),
        company_name=_trim_text(company_name, 255),
        product_description=_trim_text(product_description, 1000),
        company_industry=_trim_text(company_industry, 255),
        target_market=_trim_text(target_market, 255),
        inbound_reply=_trim_text(inbound_reply, 4000),
        reply_category=_trim_text(reply_category, 50),
        classification_reason=_trim_text(classification_reason, 1000),
        latest_outbound_subject=_trim_text(latest_outbound_subject or "", 255) or None,
        latest_outbound_body=_trim_text(latest_outbound_body or "", 2000) or None,
        meeting_link=_trim_text(meeting_link or "", 1000) or None,
    )
    payload = _call_claude(prompt)

    subject = _trim_text(payload.subject, 255)
    body = _trim_text(payload.body, 5000)
    reply_goal = _trim_text(payload.reply_goal, 50).lower()

    if reply_goal not in {"send_info", "answer_question", "propose_meeting"}:
        reply_goal = "answer_question"
    if reply_category == "INTERESTED" and meeting_link:
        reply_goal = "propose_meeting"
    if not subject:
        subject = "Re: Thanks for the reply"
    if not body:
        raise ReplyGenerationServiceError(
            "Claude did not return a usable reply body.", status_code=502
        )

    return ClaudeGeneratedReplyPayload(
        subject=subject,
        body=body,
        reply_goal=reply_goal,
    )


def ensure_generated_reply(
    db: Session,
    email_reply: EmailReply,
    classification: ReplyClassification,
    *,
    meeting_link: str | None = None,
) -> GeneratedReply | None:
    generated_reply = (
        db.query(GeneratedReply)
        .filter(GeneratedReply.email_reply_id == email_reply.id)
        .first()
    )
    if generated_reply:
        return generated_reply

    if not category_allows_generated_reply(classification.category):
        return None

    company_profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.workspace_id == email_reply.lead.workspace_id)
        .first()
    )
    if not company_profile:
        raise ReplyGenerationServiceError(
            "Complete company profile before generating reply suggestions.",
            status_code=400,
        )

    outbound_context = _latest_outbound_context(db, email_reply)
    try:
        payload = generate_reply(
            lead_name=email_reply.lead.name,
            lead_role=email_reply.lead.role,
            lead_company=email_reply.lead.company,
            company_name=company_profile.company_name,
            product_description=company_profile.product_description,
            company_industry=company_profile.industry,
            target_market=company_profile.target_market,
            inbound_reply=email_reply.reply_body,
            reply_category=classification.category,
            classification_reason=classification.reason,
            latest_outbound_subject=outbound_context.subject,
            latest_outbound_body=outbound_context.body,
            meeting_link=meeting_link,
        )
    except Exception:
        record_api_usage(
            db,
            workspace_id=email_reply.lead.workspace_id,
            provider="anthropic",
            feature="reply_generation",
            model_name=settings.anthropic_model,
            success=False,
            metadata={"lead_id": email_reply.lead_id, "reply_id": email_reply.id},
        )
        raise
    record_api_usage(
        db,
        workspace_id=email_reply.lead.workspace_id,
        provider="anthropic",
        feature="reply_generation",
        model_name=settings.anthropic_model,
        success=True,
        metadata={"lead_id": email_reply.lead_id, "reply_id": email_reply.id},
    )

    generated_reply = GeneratedReply(
        email_reply_id=email_reply.id,
        lead_id=email_reply.lead_id,
        subject=payload.subject,
        body=payload.body,
        reply_goal=payload.reply_goal,
    )
    db.add(generated_reply)
    db.flush()
    return generated_reply
