from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings


DEFAULT_SEQUENCE = [
    (1, "introduction"),
    (2, "reminder"),
    (3, "new insight"),
    (4, "final message"),
]
DEFAULT_DAY_OFFSETS = {
    1: 0,
    2: 3,
    3: 7,
    4: 12,
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _trim_text(value: str, limit: int) -> str:
    return _clean_text(value)[:limit]


class FollowupGenerationServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ClaudeFollowupItemPayload(BaseModel):
    step_number: int
    email_subject: str
    email_body: str


class ClaudeFollowupSequencePayload(BaseModel):
    items: list[ClaudeFollowupItemPayload] = Field(default_factory=list)


@dataclass
class FollowupDraft:
    step_number: int
    email_subject: str
    email_body: str
    scheduled_date: datetime


def _extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        raise FollowupGenerationServiceError(
            "Claude returned an empty follow-up response.", status_code=502
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


def _build_sequence_plan(
    followup_delay_days: int | None = None,
) -> list[tuple[int, str, int]]:
    if followup_delay_days is None:
        return [
            (step_number, label, DEFAULT_DAY_OFFSETS[step_number])
            for step_number, label in DEFAULT_SEQUENCE
        ]

    return [
        (step_number, label, followup_delay_days * step_number)
        for step_number, label in DEFAULT_SEQUENCE
    ]


def _call_claude(prompt: str) -> ClaudeFollowupSequencePayload:
    if not settings.anthropic_api_key:
        raise FollowupGenerationServiceError(
            "ANTHROPIC_API_KEY is not configured.", status_code=500
        )

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise FollowupGenerationServiceError(
            "Anthropic SDK is not installed. Run `pip install -r requirements.txt`.",
            status_code=500,
        ) from exc

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2200,
            temperature=0.5,
            system=(
                "You write concise, personalized B2B follow-up sequences. "
                "Always return valid JSON only."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise FollowupGenerationServiceError(
            f"Claude request failed for model `{settings.anthropic_model}`: {exc}",
            status_code=502,
        ) from exc

    payload_text = _extract_json_payload(_extract_response_text(message))
    try:
        return ClaudeFollowupSequencePayload.model_validate_json(payload_text)
    except ValidationError as exc:
        raise FollowupGenerationServiceError(
            "Claude returned an invalid JSON payload for follow-up generation.",
            status_code=502,
        ) from exc


def _build_prompt(
    *,
    lead_name: str,
    lead_role: str,
    lead_company: str,
    company_name: str,
    product_description: str,
    company_industry: str,
    target_market: str,
    sales_angle: str,
    value_proposition: str,
    personalization_notes: str,
    message_tone: str,
    cta_type: str,
    target_icp: str,
    initial_subject: str | None,
    initial_body: str | None,
    followup_delay_days: int | None,
) -> str:
    sequence_plan = _build_sequence_plan(followup_delay_days)
    sequence_summary = " | ".join(
        f"Step {step}: {label} (+{day_offset} days)"
        for step, label, day_offset in sequence_plan
    )

    return f"""
Write a 4-step B2B outreach sequence for one lead.

Return exactly one JSON object with this shape:
{{
  "items": [
    {{
      "step_number": 1,
      "email_subject": "...",
      "email_body": "..."
    }}
  ]
}}

Rules:
- Output valid JSON only.
- Do not include markdown or code fences.
- Return exactly 4 items for steps 1 through 4.
- The sequence should follow this structure: {sequence_summary}
- Each subject must be under 80 characters.
- Each email body must be plain text, under 1000 characters, and sound natural.
- Use the requested tone throughout the sequence.
- Avoid repetition across steps.
- Progress the follow-ups naturally from intro to reminder to new insight to final message.
- Include one clear CTA aligned to the CTA type in each email.
- Do not invent facts.

Lead profile:
- Name: {lead_name or "there"}
- Role: {lead_role}
- Company: {lead_company}

Our company profile:
- Company name: {company_name}
- Product description: {product_description}
- Industry: {company_industry}
- Target market: {target_market}

Sales insight:
- Sales angle: {sales_angle}
- Value proposition: {value_proposition}
- Personalization notes: {personalization_notes}

Campaign:
- Target ICP: {target_icp}
- Message tone: {message_tone}
- CTA type: {cta_type}

Existing initial email subject: {initial_subject or "None"}
Existing initial email body: {initial_body or "None"}
""".strip()


def generate_followup_sequence(
    *,
    lead_name: str,
    lead_role: str,
    lead_company: str,
    company_name: str,
    product_description: str,
    company_industry: str,
    target_market: str,
    sales_angle: str,
    value_proposition: str,
    personalization_notes: str,
    message_tone: str,
    cta_type: str,
    target_icp: str,
    initial_subject: str | None,
    initial_body: str | None,
    start_date: datetime | None = None,
    followup_delay_days: int | None = None,
) -> list[FollowupDraft]:
    if not _clean_text(lead_role):
        raise FollowupGenerationServiceError("Lead role is required.", status_code=400)
    if not _clean_text(company_name):
        raise FollowupGenerationServiceError(
            "Company profile is incomplete.", status_code=400
        )

    prompt = _build_prompt(
        lead_name=_trim_text(lead_name, 255),
        lead_role=_trim_text(lead_role, 255),
        lead_company=_trim_text(lead_company, 255),
        company_name=_trim_text(company_name, 255),
        product_description=_trim_text(product_description, 1000),
        company_industry=_trim_text(company_industry, 255),
        target_market=_trim_text(target_market, 255),
        sales_angle=_trim_text(sales_angle, 1000),
        value_proposition=_trim_text(value_proposition, 1000),
        personalization_notes=_trim_text(personalization_notes, 1500),
        message_tone=_trim_text(message_tone, 255),
        cta_type=_trim_text(cta_type, 255),
        target_icp=_trim_text(target_icp, 255),
        initial_subject=_trim_text(initial_subject or "", 255) or None,
        initial_body=_trim_text(initial_body or "", 1500) or None,
        followup_delay_days=followup_delay_days,
    )
    payload = _call_claude(prompt)

    items_by_step = {item.step_number: item for item in payload.items}
    missing_steps = [
        step for step, _ in DEFAULT_SEQUENCE if step not in items_by_step
    ]
    if missing_steps:
        raise FollowupGenerationServiceError(
            "Claude did not return all required follow-up steps.", status_code=502
        )

    base_time = start_date or datetime.utcnow()
    drafts: list[FollowupDraft] = []
    for step_number, label, day_offset in _build_sequence_plan(followup_delay_days):
        item = items_by_step[step_number]
        subject = _trim_text(item.email_subject, 255)
        body = _trim_text(item.email_body, 5000)

        if not subject:
            subject = f"{label.title()} follow-up"
        if not body:
            raise FollowupGenerationServiceError(
                f"Claude did not return a usable body for step {step_number}.",
                status_code=502,
            )

        drafts.append(
            FollowupDraft(
                step_number=step_number,
                email_subject=subject,
                email_body=body,
                scheduled_date=base_time + timedelta(days=day_offset),
            )
        )

    return drafts
