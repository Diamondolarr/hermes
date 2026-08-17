from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_reply import EmailReply
from app.models.meeting import Meeting
from app.models.reply_classification import ReplyClassification


class MeetingSchedulingServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _get_scheduling_link() -> str:
    link = settings.calendly_scheduling_link.strip()
    if not link:
        raise MeetingSchedulingServiceError(
            "CALENDLY_SCHEDULING_LINK is not configured.", status_code=500
        )
    return link


def ensure_meeting_for_interested_reply(
    db: Session,
    email_reply: EmailReply,
    classification: ReplyClassification,
) -> Meeting | None:
    if classification.category != "INTERESTED":
        return None

    meeting_link = _get_scheduling_link()
    meeting = db.query(Meeting).filter(Meeting.lead_id == email_reply.lead_id).first()
    if meeting:
        meeting.meeting_link = meeting_link
        meeting.status = "LINK_SENT"
        return meeting

    meeting = Meeting(
        lead_id=email_reply.lead_id,
        scheduled_time=None,
        meeting_link=meeting_link,
        status="LINK_SENT",
    )
    db.add(meeting)
    db.flush()
    return meeting
