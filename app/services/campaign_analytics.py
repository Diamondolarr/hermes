from dataclasses import dataclass
import re

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.email_reply import EmailReply
from app.models.meeting import Meeting
from app.models.reply_classification import ReplyClassification
from app.models.sent_email import SentEmail
from app.services.admin_monitoring import record_api_usage_event


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _trim_text(value: str, limit: int) -> str:
    return _clean_text(value)[:limit]


def _extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        raise ValueError("Gemini returned an empty analytics response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        return match.group(0)
    return text


def _format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def _build_reply_breakdown_text(reply_breakdown: dict[str, int]) -> str:
    ordered_categories = [
        "INTERESTED",
        "REQUEST_INFO",
        "REFERRAL",
        "NOT_INTERESTED",
        "UNSUBSCRIBE",
        "OTHER",
    ]
    parts: list[str] = []
    for category in ordered_categories:
        count = reply_breakdown.get(category, 0)
        if count:
            parts.append(f"{category}: {count}")
    return " | ".join(parts) if parts else "No classified replies yet."


class GeminiCampaignAnalyticsPayload(BaseModel):
    ai_summary: str
    ai_recommendations: list[str] = Field(default_factory=list)


@dataclass
class CampaignAnalyticsMetrics:
    emails_sent: int
    emails_replied: int
    reply_rate: float
    meetings_booked: int
    conversion_rate: float
    reply_breakdown: dict[str, int]


@dataclass
class CampaignAnalyticsResult:
    campaign_id: str
    campaign_name: str
    status: str
    emails_sent: int
    emails_replied: int
    reply_rate: float
    meetings_booked: int
    conversion_rate: float
    ai_summary: str
    ai_recommendations: list[str]


def _reply_join_condition():
    return or_(
        and_(
            SentEmail.thread_id.is_not(None),
            EmailReply.thread_id == SentEmail.thread_id,
            or_(
                SentEmail.email_account_id.is_(None),
                EmailReply.email_account_id == SentEmail.email_account_id,
            ),
        ),
        and_(
            SentEmail.thread_id.is_(None),
            EmailReply.lead_id == SentEmail.lead_id,
        ),
    )


def _compute_metrics(db: Session, campaign: Campaign) -> CampaignAnalyticsMetrics:
    emails_sent = int(
        db.query(func.count(SentEmail.id))
        .filter(SentEmail.campaign_id == campaign.id, SentEmail.status == "SENT")
        .scalar()
        or 0
    )

    reply_match_condition = _reply_join_condition()
    emails_replied = int(
        db.query(func.count(func.distinct(SentEmail.lead_id)))
        .select_from(SentEmail)
        .join(EmailReply, reply_match_condition)
        .filter(SentEmail.campaign_id == campaign.id, SentEmail.status == "SENT")
        .scalar()
        or 0
    )

    breakdown_rows = (
        db.query(
            ReplyClassification.category,
            func.count(func.distinct(EmailReply.id)),
        )
        .select_from(SentEmail)
        .join(EmailReply, reply_match_condition)
        .join(
            ReplyClassification,
            ReplyClassification.email_reply_id == EmailReply.id,
        )
        .filter(SentEmail.campaign_id == campaign.id, SentEmail.status == "SENT")
        .group_by(ReplyClassification.category)
        .all()
    )
    reply_breakdown = {category: int(count) for category, count in breakdown_rows}

    meetings_booked = int(
        db.query(func.count(func.distinct(Meeting.lead_id)))
        .select_from(SentEmail)
        .join(Meeting, Meeting.lead_id == SentEmail.lead_id)
        .filter(
            SentEmail.campaign_id == campaign.id,
            SentEmail.status == "SENT",
            Meeting.status == "BOOKED",
        )
        .scalar()
        or 0
    )

    reply_rate = round(
        (emails_replied / emails_sent) if emails_sent else 0.0,
        4,
    )
    conversion_rate = round(
        (meetings_booked / emails_sent) if emails_sent else 0.0,
        4,
    )

    return CampaignAnalyticsMetrics(
        emails_sent=emails_sent,
        emails_replied=emails_replied,
        reply_rate=reply_rate,
        meetings_booked=meetings_booked,
        conversion_rate=conversion_rate,
        reply_breakdown=reply_breakdown,
    )


def _build_prompt(campaign: Campaign, metrics: CampaignAnalyticsMetrics) -> str:
    return f"""
You are an SDR campaign analyst.

Review the campaign metrics and write a concise performance summary plus practical next-step recommendations.

Return exactly one JSON object with these keys:
- ai_summary
- ai_recommendations

Rules:
- Output valid JSON only.
- Do not include markdown or code fences.
- ai_summary should be concise, grounded in the metrics, and under 500 characters.
- ai_recommendations must be an array with 2 to 4 short, actionable strings.
- Do not invent data that is not provided.
- Note that meetings_booked only counts meetings whose status is BOOKED. LINK_SENT does not count as booked.

Campaign name: {campaign.name}
Campaign status: {campaign.status}
Campaign target ICP: {campaign.target_icp}
Campaign tone: {campaign.message_tone}
Campaign CTA type: {campaign.cta_type}

emails_sent: {metrics.emails_sent}
emails_replied: {metrics.emails_replied}
reply_rate: {_format_rate(metrics.reply_rate)}
meetings_booked: {metrics.meetings_booked}
conversion_rate: {_format_rate(metrics.conversion_rate)}
reply_classification_breakdown: {_build_reply_breakdown_text(metrics.reply_breakdown)}
""".strip()


def _fallback_analytics_narrative(
    campaign: Campaign, metrics: CampaignAnalyticsMetrics
) -> GeminiCampaignAnalyticsPayload:
    if metrics.emails_sent == 0:
        summary = (
            f"{campaign.name} has not sent any emails yet, so there is not enough live "
            "campaign activity to evaluate reply or conversion performance."
        )
        recommendations = [
            "Schedule leads into the campaign to create a performance baseline.",
            "Review tone and CTA before launching so early sends are easier to learn from.",
        ]
        return GeminiCampaignAnalyticsPayload(
            ai_summary=_trim_text(summary, 500),
            ai_recommendations=recommendations,
        )

    summary_parts = [
        f"{campaign.name} has sent {metrics.emails_sent} emails and received replies from {metrics.emails_replied} leads",
        f"for a reply rate of {_format_rate(metrics.reply_rate)}.",
    ]
    if metrics.meetings_booked:
        summary_parts.append(
            f"It has booked {metrics.meetings_booked} meetings, producing a conversion rate of {_format_rate(metrics.conversion_rate)}."
        )
    else:
        summary_parts.append(
            "No meetings are marked as BOOKED yet, so conversion is still at 0.0%."
        )

    recommendations: list[str] = []
    if metrics.reply_rate < 0.05:
        recommendations.append(
            "Refresh the subject line and first-line personalization to lift reply volume."
        )
    elif metrics.reply_rate < 0.15:
        recommendations.append(
            "Review the strongest positive replies and reuse that language in new outreach."
        )
    else:
        recommendations.append(
            "Double down on the current angle and test small CTA tweaks instead of a full rewrite."
        )

    interested_signals = (
        metrics.reply_breakdown.get("INTERESTED", 0)
        + metrics.reply_breakdown.get("REQUEST_INFO", 0)
        + metrics.reply_breakdown.get("REFERRAL", 0)
    )
    if interested_signals:
        recommendations.append(
            "Prioritize the interested and information-seeking replies with fast, specific follow-up."
        )
    else:
        recommendations.append(
            "Tighten the value proposition so replies move beyond neutral or no-response patterns."
        )

    if metrics.meetings_booked == 0:
        recommendations.append(
            "Check that meeting links are being sent clearly and that booked meetings are updated from LINK_SENT to BOOKED."
        )
    else:
        recommendations.append(
            "Look at the leads that booked meetings and mirror their role and company traits in targeting."
        )

    return GeminiCampaignAnalyticsPayload(
        ai_summary=_trim_text(" ".join(summary_parts), 500),
        ai_recommendations=recommendations[:4],
    )


def _generate_ai_narrative(
    db: Session, campaign: Campaign, metrics: CampaignAnalyticsMetrics
) -> GeminiCampaignAnalyticsPayload:
    if not settings.gemini_api_key:
        return _fallback_analytics_narrative(campaign, metrics)

    try:
        from google import genai
    except ImportError:
        return _fallback_analytics_narrative(campaign, metrics)

    model_name = settings.gemini_analytics_model or settings.gemini_model
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=_build_prompt(campaign, metrics),
            config={"temperature": 0.2},
        )
        payload_text = _extract_json_payload(getattr(response, "text", "") or "")
        payload = GeminiCampaignAnalyticsPayload.model_validate_json(payload_text)
    except Exception:
        record_api_usage_event(
            workspace_id=campaign.workspace_id,
            provider="gemini",
            feature="campaign_analytics",
            model_name=model_name,
            success=False,
            metadata={"campaign_id": campaign.id},
        )
        return _fallback_analytics_narrative(campaign, metrics)
    record_api_usage_event(
        workspace_id=campaign.workspace_id,
        provider="gemini",
        feature="campaign_analytics",
        model_name=model_name,
        success=True,
        metadata={"campaign_id": campaign.id},
    )

    summary = _trim_text(payload.ai_summary, 500)
    if not summary:
        return _fallback_analytics_narrative(campaign, metrics)

    recommendations = [
        _trim_text(item, 200)
        for item in payload.ai_recommendations
        if _trim_text(item, 200)
    ][:4]
    if not recommendations:
        return _fallback_analytics_narrative(campaign, metrics)

    try:
        return GeminiCampaignAnalyticsPayload(
            ai_summary=summary,
            ai_recommendations=recommendations,
        )
    except ValidationError:
        return _fallback_analytics_narrative(campaign, metrics)


def get_campaign_analytics(db: Session, campaign: Campaign) -> CampaignAnalyticsResult:
    metrics = _compute_metrics(db, campaign)
    narrative = _generate_ai_narrative(db, campaign, metrics)

    return CampaignAnalyticsResult(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        status=campaign.status,
        emails_sent=metrics.emails_sent,
        emails_replied=metrics.emails_replied,
        reply_rate=metrics.reply_rate,
        meetings_booked=metrics.meetings_booked,
        conversion_rate=metrics.conversion_rate,
        ai_summary=narrative.ai_summary,
        ai_recommendations=narrative.ai_recommendations,
    )
