from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.campaign_insight import CampaignInsight
from app.models.email_reply import EmailReply
from app.models.lead import Lead
from app.models.sent_email import SentEmail
from app.services.admin_monitoring import record_api_usage


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _trim_text(value: str, limit: int) -> str:
    return _clean_text(value)[:limit]


def _extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        raise ValueError("Gemini returned an empty campaign insights response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        return match.group(0)
    return text


def _format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def _normalize_subject(subject: str | None) -> str:
    cleaned = _trim_text(subject or "", 255)
    return cleaned or "(No subject)"


def _resolve_timezone(timezone_name: str | None) -> ZoneInfo:
    candidate = (timezone_name or "").strip() or "UTC"
    try:
        return ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _to_campaign_timezone(sent_at: datetime, timezone_name: str | None) -> datetime:
    value = sent_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(_resolve_timezone(timezone_name))


def _format_send_bucket(sent_at: datetime, timezone_name: str | None) -> str:
    local_dt = _to_campaign_timezone(sent_at, timezone_name)
    timezone_label = (timezone_name or "UTC").strip() or "UTC"
    return f"{local_dt.hour:02d}:00-{local_dt.hour:02d}:59 {timezone_label}"


def _candidate_score(sent_count: int, replied_count: int) -> float:
    return (replied_count + 1.0) / (sent_count + 2.0)


@dataclass
class InsightCandidate:
    label: str
    sent_count: int
    replied_count: int
    reply_rate: float
    score: float


@dataclass
class CampaignInsightSignals:
    emails_sent: int
    emails_replied: int
    top_subject_lines: list[InsightCandidate]
    top_send_times: list[InsightCandidate]
    top_industries: list[InsightCandidate]


class GeminiCampaignInsightsPayload(BaseModel):
    best_subject_line: str
    best_send_time: str
    best_industry_response: str
    summary: str
    recommendations: list[str] = Field(default_factory=list)


def _build_candidates(counter: dict[str, dict[str, int]]) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []
    for label, stats in counter.items():
        sent_count = int(stats.get("sent", 0))
        replied_count = int(stats.get("replied", 0))
        if sent_count <= 0:
            continue
        reply_rate = replied_count / sent_count
        candidates.append(
            InsightCandidate(
                label=label,
                sent_count=sent_count,
                replied_count=replied_count,
                reply_rate=round(reply_rate, 4),
                score=round(_candidate_score(sent_count, replied_count), 4),
            )
        )

    return sorted(
        candidates,
        key=lambda item: (item.score, item.reply_rate, item.sent_count, item.label),
        reverse=True,
    )


def _format_candidate_list(
    candidates: list[InsightCandidate], *, empty_message: str
) -> str:
    if not candidates:
        return empty_message
    parts: list[str] = []
    for item in candidates[:5]:
        parts.append(
            f"{item.label} (sent={item.sent_count}, replied={item.replied_count}, reply_rate={_format_rate(item.reply_rate)})"
        )
    return " | ".join(parts)


def _compute_signals(db: Session, campaign: Campaign) -> CampaignInsightSignals:
    sent_emails = (
        db.query(SentEmail)
        .options(joinedload(SentEmail.lead).joinedload(Lead.company_record))
        .filter(SentEmail.campaign_id == campaign.id, SentEmail.status == "SENT")
        .order_by(SentEmail.sent_at.asc())
        .all()
    )

    lead_ids = {item.lead_id for item in sent_emails}
    replies = (
        db.query(EmailReply)
        .filter(EmailReply.lead_id.in_(lead_ids))
        .order_by(EmailReply.received_at.asc())
        .all()
        if lead_ids
        else []
    )

    replies_by_lead: dict[str, list[EmailReply]] = defaultdict(list)
    replies_by_thread_and_account: dict[tuple[str, str], list[EmailReply]] = defaultdict(
        list
    )
    replies_by_thread: dict[str, list[EmailReply]] = defaultdict(list)

    for reply in replies:
        replies_by_lead[reply.lead_id].append(reply)
        if reply.thread_id:
            replies_by_thread[reply.thread_id].append(reply)
            replies_by_thread_and_account[
                (reply.thread_id, reply.email_account_id)
            ].append(reply)

    subject_counter: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sent": 0, "replied": 0}
    )
    send_time_counter: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sent": 0, "replied": 0}
    )
    industry_counter: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sent": 0, "replied": 0}
    )

    replied_leads: set[str] = set()

    for sent_email in sent_emails:
        replied = False
        if sent_email.thread_id:
            if sent_email.email_account_id:
                replied = bool(
                    replies_by_thread_and_account.get(
                        (sent_email.thread_id, sent_email.email_account_id)
                    )
                )
            else:
                replied = bool(replies_by_thread.get(sent_email.thread_id))
        else:
            replied = bool(replies_by_lead.get(sent_email.lead_id))

        subject_label = _normalize_subject(sent_email.email_subject)
        send_time_label = _format_send_bucket(
            sent_email.sent_at, campaign.send_timezone
        )
        industry_label = "Unknown"
        if sent_email.lead and sent_email.lead.company_record:
            industry_label = (
                _trim_text(sent_email.lead.company_record.industry or "", 255)
                or "Unknown"
            )

        subject_counter[subject_label]["sent"] += 1
        send_time_counter[send_time_label]["sent"] += 1
        industry_counter[industry_label]["sent"] += 1

        if replied:
            replied_leads.add(sent_email.lead_id)
            subject_counter[subject_label]["replied"] += 1
            send_time_counter[send_time_label]["replied"] += 1
            industry_counter[industry_label]["replied"] += 1

    return CampaignInsightSignals(
        emails_sent=len(sent_emails),
        emails_replied=len(replied_leads),
        top_subject_lines=_build_candidates(subject_counter),
        top_send_times=_build_candidates(send_time_counter),
        top_industries=_build_candidates(industry_counter),
    )


def _build_prompt(campaign: Campaign, signals: CampaignInsightSignals) -> str:
    return f"""
You are an SDR performance analyst.

Review the aggregated campaign data and identify the strongest patterns.

Return exactly one JSON object with these keys:
- best_subject_line
- best_send_time
- best_industry_response
- summary
- recommendations

Rules:
- Output valid JSON only.
- Do not include markdown or code fences.
- Favor patterns with stronger sample sizes over one-off wins.
- If the data is thin, mention the limited confidence in the summary.
- best_subject_line, best_send_time, and best_industry_response should each be short strings under 255 characters.
- summary should stay under 600 characters.
- recommendations must be an array of 2 to 4 short, practical strings.
- Use only the provided aggregated data.

Campaign name: {campaign.name}
Campaign status: {campaign.status}
Campaign target ICP: {campaign.target_icp}
Campaign tone: {campaign.message_tone}
Campaign CTA type: {campaign.cta_type}

emails_sent: {signals.emails_sent}
emails_replied: {signals.emails_replied}

Subject line performance:
{_format_candidate_list(signals.top_subject_lines, empty_message="No sent email subject data yet.")}

Send time performance:
{_format_candidate_list(signals.top_send_times, empty_message="No send time performance data yet.")}

Industry performance:
{_format_candidate_list(signals.top_industries, empty_message="No industry performance data yet.")}
""".strip()


def _fallback_generate_payload(
    campaign: Campaign, signals: CampaignInsightSignals
) -> GeminiCampaignInsightsPayload:
    if signals.emails_sent == 0:
        return GeminiCampaignInsightsPayload(
            best_subject_line="Insufficient data",
            best_send_time="Insufficient data",
            best_industry_response="Insufficient data",
            summary=(
                f"{campaign.name} has not sent any emails yet, so there is not enough "
                "campaign activity to identify winning subject lines, send times, or industries."
            ),
            recommendations=[
                "Schedule and send the first batch so the system has real performance data to learn from.",
                "Use at least a few subject line and timing variations to make future insights more meaningful.",
            ],
        )

    best_subject = (
        signals.top_subject_lines[0].label
        if signals.top_subject_lines
        else "Insufficient data"
    )
    best_send_time = (
        signals.top_send_times[0].label
        if signals.top_send_times
        else "Insufficient data"
    )
    best_industry = (
        signals.top_industries[0].label
        if signals.top_industries
        else "Insufficient data"
    )

    low_data_note = (
        " Confidence is limited because the campaign has only a small amount of send data."
        if signals.emails_sent < 5
        else ""
    )
    summary = (
        f"{campaign.name} has sent {signals.emails_sent} emails and received replies from "
        f"{signals.emails_replied} leads. The strongest current subject line is {best_subject}, "
        f"the best-performing send window is {best_send_time}, and the most responsive industry is "
        f"{best_industry}.{low_data_note}"
    )

    recommendations = [
        "Reuse the current best subject line as the control and test one focused variant against it.",
        "Concentrate sends around the best-performing time block before expanding into new windows.",
    ]
    if best_industry != "Insufficient data":
        recommendations.append(
            f"Prioritize leads in {best_industry} while the response pattern is strongest there."
        )
    else:
        recommendations.append(
            "Research more lead companies so industry-level response patterns become clearer."
        )

    return GeminiCampaignInsightsPayload(
        best_subject_line=_trim_text(best_subject, 255) or "Insufficient data",
        best_send_time=_trim_text(best_send_time, 255) or "Insufficient data",
        best_industry_response=_trim_text(best_industry, 255) or "Insufficient data",
        summary=_trim_text(summary, 600),
        recommendations=[_trim_text(item, 200) for item in recommendations[:4]],
    )


def _generate_payload(
    db: Session, campaign: Campaign, signals: CampaignInsightSignals
) -> GeminiCampaignInsightsPayload:
    if not settings.gemini_api_key:
        return _fallback_generate_payload(campaign, signals)

    try:
        from google import genai
    except ImportError:
        return _fallback_generate_payload(campaign, signals)

    model_name = settings.gemini_analytics_model or settings.gemini_model
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=_build_prompt(campaign, signals),
            config={"temperature": 0.2},
        )
        payload_text = _extract_json_payload(getattr(response, "text", "") or "")
        payload = GeminiCampaignInsightsPayload.model_validate_json(payload_text)
    except Exception:
        record_api_usage(
            db,
            workspace_id=campaign.workspace_id,
            provider="gemini",
            feature="campaign_insights",
            model_name=model_name,
            success=False,
            metadata={"campaign_id": campaign.id},
        )
        return _fallback_generate_payload(campaign, signals)
    record_api_usage(
        db,
        workspace_id=campaign.workspace_id,
        provider="gemini",
        feature="campaign_insights",
        model_name=model_name,
        success=True,
        metadata={"campaign_id": campaign.id},
    )

    recommendations = [
        _trim_text(item, 200)
        for item in payload.recommendations
        if _trim_text(item, 200)
    ][:4]
    if len(recommendations) < 2:
        return _fallback_generate_payload(campaign, signals)

    try:
        return GeminiCampaignInsightsPayload(
            best_subject_line=_trim_text(payload.best_subject_line, 255)
            or "Insufficient data",
            best_send_time=_trim_text(payload.best_send_time, 255)
            or "Insufficient data",
            best_industry_response=_trim_text(payload.best_industry_response, 255)
            or "Insufficient data",
            summary=_trim_text(payload.summary, 600)
            or _fallback_generate_payload(campaign, signals).summary,
            recommendations=recommendations,
        )
    except ValidationError:
        return _fallback_generate_payload(campaign, signals)


def generate_campaign_insight(db: Session, campaign: Campaign) -> CampaignInsight:
    signals = _compute_signals(db, campaign)
    payload = _generate_payload(db, campaign, signals)

    insight = (
        db.query(CampaignInsight)
        .filter(CampaignInsight.campaign_id == campaign.id)
        .first()
    )
    if insight:
        insight.best_subject_line = payload.best_subject_line
        insight.best_send_time = payload.best_send_time
        insight.best_industry_response = payload.best_industry_response
        insight.summary = payload.summary
        insight.recommendations = payload.recommendations
        insight.generated_at = datetime.utcnow()
    else:
        insight = CampaignInsight(
            campaign_id=campaign.id,
            best_subject_line=payload.best_subject_line,
            best_send_time=payload.best_send_time,
            best_industry_response=payload.best_industry_response,
            summary=payload.summary,
            recommendations=payload.recommendations,
            generated_at=datetime.utcnow(),
        )
        db.add(insight)

    db.flush()
    return insight
