import re

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _trim_text(value: str, limit: int) -> str:
    return _clean_text(value)[:limit]


class LeadResearchServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiLeadInsightPayload(BaseModel):
    role_category: str
    possible_pain_points: list[str] = Field(default_factory=list)
    recommended_sales_angle: str
    confidence_score: float


def _extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        raise LeadResearchServiceError(
            "Gemini returned an empty lead research response.", status_code=502
        )

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        return match.group(0)
    return text


def _call_gemini(prompt: str) -> GeminiLeadInsightPayload:
    if not settings.gemini_api_key:
        raise LeadResearchServiceError(
            "GEMINI_API_KEY is not configured.", status_code=500
        )

    try:
        from google import genai
    except ImportError as exc:
        raise LeadResearchServiceError(
            "Gemini SDK is not installed. Run `pip install -r requirements.txt`.",
            status_code=500,
        ) from exc

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"temperature": 0.2},
        )
    except Exception as exc:
        raise LeadResearchServiceError(
            f"Gemini request failed for model `{settings.gemini_model}`: {exc}",
            status_code=502,
        ) from exc

    payload_text = _extract_json_payload(getattr(response, "text", "") or "")
    try:
        payload = GeminiLeadInsightPayload.model_validate_json(payload_text)
    except ValidationError as exc:
        raise LeadResearchServiceError(
            "Gemini returned an invalid JSON payload for lead research.",
            status_code=502,
        ) from exc

    return payload


def _build_prompt(
    lead_name: str,
    lead_role: str,
    company_name: str,
    company_industry: str | None,
    company_description: str | None,
    product_summary: str | None,
) -> str:
    has_company_context = any(
        [
            company_name,
            company_industry,
            company_description,
            product_summary,
        ]
    )

    context_note = (
        "Use both the lead role and the company context to infer likely responsibilities, business challenges, and the best sales angle."
        if has_company_context
        else "Company research is unavailable. Use only the lead role and company name to infer likely responsibilities, business challenges, and the best sales angle."
    )

    return f"""
You are a B2B SDR research assistant.

{context_note}

Return exactly one JSON object with these keys:
- role_category
- possible_pain_points
- recommended_sales_angle
- confidence_score

Rules:
- Output valid JSON only.
- Do not include markdown or code fences.
- role_category should be a concise department or function label.
- possible_pain_points must be an array of 2 to 5 short strings.
- recommended_sales_angle should be specific and under 300 characters.
- confidence_score must be a number between 0.0 and 1.0.
- Base the answer on reasonable business inference from the provided context only.

Lead name: {lead_name or "Unknown"}
Lead role: {lead_role}
Company name: {company_name or "Unknown"}
Company industry: {company_industry or "Unknown"}
Company description: {company_description or "Unknown"}
Company product summary: {product_summary or "Unknown"}
""".strip()


def generate_lead_insight(
    *,
    lead_name: str,
    lead_role: str,
    company_name: str,
    company_industry: str | None,
    company_description: str | None,
    product_summary: str | None,
) -> GeminiLeadInsightPayload:
    cleaned_role = _clean_text(lead_role)
    if not cleaned_role:
        raise LeadResearchServiceError("Lead role is required.", status_code=400)

    prompt = _build_prompt(
        lead_name=_clean_text(lead_name),
        lead_role=cleaned_role,
        company_name=_clean_text(company_name),
        company_industry=_trim_text(company_industry or "", 255) or None,
        company_description=_trim_text(company_description or "", 1500) or None,
        product_summary=_trim_text(product_summary or "", 800) or None,
    )
    payload = _call_gemini(prompt)

    role_category = _trim_text(payload.role_category, 255) or "Unknown"
    pain_points = [
        _trim_text(point, 255)
        for point in payload.possible_pain_points
        if _trim_text(point, 255)
    ]
    if not pain_points:
        pain_points = ["Unclear priorities", "Need to improve business outcomes"]

    sales_angle = _trim_text(payload.recommended_sales_angle, 1000)
    if not sales_angle:
        sales_angle = (
            f"Lead with a role-relevant outcome for the {role_category.lower()} function."
        )

    confidence = max(0.0, min(1.0, float(payload.confidence_score)))

    return GeminiLeadInsightPayload(
        role_category=role_category,
        possible_pain_points=pain_points[:5],
        recommended_sales_angle=sales_angle,
        confidence_score=confidence,
    )
