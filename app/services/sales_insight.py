import re

from pydantic import BaseModel, ValidationError

from app.core.config import settings


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _trim_text(value: str, limit: int) -> str:
    return _clean_text(value)[:limit]


class SalesInsightServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiSalesInsightPayload(BaseModel):
    sales_angle: str
    value_proposition: str
    personalization_notes: str


def _extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        raise SalesInsightServiceError(
            "Gemini returned an empty sales insight response.", status_code=502
        )

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        return match.group(0)
    return text


def _call_gemini(prompt: str) -> GeminiSalesInsightPayload:
    if not settings.gemini_api_key:
        raise SalesInsightServiceError(
            "GEMINI_API_KEY is not configured.", status_code=500
        )

    try:
        from google import genai
    except ImportError as exc:
        raise SalesInsightServiceError(
            "Gemini SDK is not installed. Run `pip install -r requirements.txt`.",
            status_code=500,
        ) from exc

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"temperature": 0.3},
        )
    except Exception as exc:
        raise SalesInsightServiceError(
            f"Gemini request failed for model `{settings.gemini_model}`: {exc}",
            status_code=502,
        ) from exc

    payload_text = _extract_json_payload(getattr(response, "text", "") or "")
    try:
        return GeminiSalesInsightPayload.model_validate_json(payload_text)
    except ValidationError as exc:
        raise SalesInsightServiceError(
            "Gemini returned an invalid JSON payload for sales insight generation.",
            status_code=502,
        ) from exc


def _build_prompt(
    *,
    lead_name: str,
    lead_role: str,
    company_name: str,
    company_industry: str | None,
    company_description: str | None,
    company_product_summary: str | None,
    role_category: str,
    possible_pain_points: list[str],
    recommended_sales_angle: str,
    confidence_score: float,
    icp_target_industry: str | None,
    icp_target_company_size: str | None,
    icp_target_roles: list[str] | None,
    icp_target_region: str | None,
    icp_pain_points: list[str] | None,
) -> str:
    icp_context = "available" if any(
        [
            icp_target_industry,
            icp_target_company_size,
            icp_target_roles,
            icp_target_region,
            icp_pain_points,
        ]
    ) else "not available"

    return f"""
You are a senior B2B SDR strategist.

Create a concise, practical outreach strategy for one lead.

Return exactly one JSON object with these keys:
- sales_angle
- value_proposition
- personalization_notes

Rules:
- Output valid JSON only.
- Do not include markdown or code fences.
- sales_angle should be a focused tactical angle under 300 characters.
- value_proposition should connect the offer to the lead's likely business outcomes and stay under 350 characters.
- personalization_notes should be specific notes an SDR can use in outreach and stay under 500 characters.
- Use the ICP when available, but do not invent missing facts.
- Ground the output in the lead role, lead insight, and company context.

Lead name: {lead_name or "Unknown"}
Lead role: {lead_role}
Lead role category: {role_category}
Lead possible pain points: {" | ".join(possible_pain_points) if possible_pain_points else "Unknown"}
Lead recommended sales angle: {recommended_sales_angle}
Lead insight confidence: {confidence_score:.2f}

Company name: {company_name or "Unknown"}
Company industry: {company_industry or "Unknown"}
Company description: {company_description or "Unknown"}
Company product summary: {company_product_summary or "Unknown"}

ICP context: {icp_context}
ICP target industry: {icp_target_industry or "Unknown"}
ICP target company size: {icp_target_company_size or "Unknown"}
ICP target roles: {" | ".join(icp_target_roles or []) if icp_target_roles else "Unknown"}
ICP target region: {icp_target_region or "Unknown"}
ICP pain points: {" | ".join(icp_pain_points or []) if icp_pain_points else "Unknown"}
""".strip()


def generate_sales_insight(
    *,
    lead_name: str,
    lead_role: str,
    company_name: str,
    company_industry: str | None,
    company_description: str | None,
    company_product_summary: str | None,
    role_category: str,
    possible_pain_points: list[str],
    recommended_sales_angle: str,
    confidence_score: float,
    icp_target_industry: str | None,
    icp_target_company_size: str | None,
    icp_target_roles: list[str] | None,
    icp_target_region: str | None,
    icp_pain_points: list[str] | None,
) -> GeminiSalesInsightPayload:
    cleaned_role = _clean_text(lead_role)
    if not cleaned_role:
        raise SalesInsightServiceError("Lead role is required.", status_code=400)

    prompt = _build_prompt(
        lead_name=_trim_text(lead_name, 255),
        lead_role=cleaned_role,
        company_name=_trim_text(company_name, 255),
        company_industry=_trim_text(company_industry or "", 255) or None,
        company_description=_trim_text(company_description or "", 1500) or None,
        company_product_summary=_trim_text(company_product_summary or "", 800) or None,
        role_category=_trim_text(role_category, 255) or "Unknown",
        possible_pain_points=[
            _trim_text(point, 255)
            for point in possible_pain_points
            if _trim_text(point, 255)
        ][:5],
        recommended_sales_angle=_trim_text(recommended_sales_angle, 600),
        confidence_score=max(0.0, min(1.0, float(confidence_score))),
        icp_target_industry=_trim_text(icp_target_industry or "", 255) or None,
        icp_target_company_size=_trim_text(icp_target_company_size or "", 255) or None,
        icp_target_roles=[
            _trim_text(role, 255)
            for role in (icp_target_roles or [])
            if _trim_text(role, 255)
        ][:10] or None,
        icp_target_region=_trim_text(icp_target_region or "", 255) or None,
        icp_pain_points=[
            _trim_text(point, 255)
            for point in (icp_pain_points or [])
            if _trim_text(point, 255)
        ][:10] or None,
    )
    payload = _call_gemini(prompt)

    sales_angle = _trim_text(payload.sales_angle, 1000)
    if not sales_angle:
        sales_angle = "Lead with a role-aligned business outcome and a concrete next-step."

    value_proposition = _trim_text(payload.value_proposition, 1000)
    if not value_proposition:
        value_proposition = (
            "Position the offer around reducing friction and improving measurable outcomes for the lead's team."
        )

    personalization_notes = _trim_text(payload.personalization_notes, 2000)
    if not personalization_notes:
        personalization_notes = (
            "Reference the lead's role, likely priorities, and the company's business context in the outreach."
        )

    return GeminiSalesInsightPayload(
        sales_angle=sales_angle,
        value_proposition=value_proposition,
        personalization_notes=personalization_notes,
    )
