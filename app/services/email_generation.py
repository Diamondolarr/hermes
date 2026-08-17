import re

from pydantic import BaseModel, ValidationError

from app.core.config import settings


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _trim_text(value: str, limit: int) -> str:
    return _clean_text(value)[:limit]


class EmailGenerationServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ClaudeEmailPayload(BaseModel):
    subject: str
    body: str


def _extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        raise EmailGenerationServiceError(
            "Claude returned an empty email generation response.", status_code=502
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


def _call_claude(prompt: str) -> ClaudeEmailPayload:
    if not settings.anthropic_api_key:
        raise EmailGenerationServiceError(
            "ANTHROPIC_API_KEY is not configured.", status_code=500
        )

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise EmailGenerationServiceError(
            "Anthropic SDK is not installed. Run `pip install -r requirements.txt`.",
            status_code=500,
        ) from exc

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=800,
            temperature=0.4,
            system=(
                "You write concise, personalized B2B cold emails. "
                "Always return valid JSON only."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise EmailGenerationServiceError(
            f"Claude request failed for model `{settings.anthropic_model}`: {exc}",
            status_code=502,
        ) from exc

    payload_text = _extract_json_payload(_extract_response_text(message))
    try:
        return ClaudeEmailPayload.model_validate_json(payload_text)
    except ValidationError as exc:
        raise EmailGenerationServiceError(
            "Claude returned an invalid JSON payload for email generation.",
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
) -> str:
    return f"""
Write a personalized cold outreach email for a B2B sales campaign.

Return exactly one JSON object with these keys:
- subject
- body

Rules:
- Output valid JSON only.
- Do not include markdown or code fences.
- Subject must be under 80 characters.
- Body must be plain text, under 1200 characters, and sound natural.
- Do not use placeholders like [First Name].
- Use the requested tone.
- Include one clear CTA aligned to the CTA type.
- Ground the message in the lead profile, sales insight, and company profile.
- Avoid exaggerated claims, fake metrics, or invented facts.

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
""".strip()


def generate_email(
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
) -> ClaudeEmailPayload:
    if not _clean_text(lead_role):
        raise EmailGenerationServiceError("Lead role is required.", status_code=400)
    if not _clean_text(company_name):
        raise EmailGenerationServiceError(
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
    )
    payload = _call_claude(prompt)

    subject = _trim_text(payload.subject, 255)
    body = _trim_text(payload.body, 5000)

    if not subject:
        subject = "Quick idea for your team"
    if not body:
        raise EmailGenerationServiceError(
            "Claude did not return a usable email body.", status_code=502
        )

    return ClaudeEmailPayload(subject=subject, body=body)
