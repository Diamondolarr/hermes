import math
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.conversation_memory import ConversationMemory
from app.models.email_reply import EmailReply
from app.models.note import Note
from app.models.sent_email import SentEmail
from app.services.admin_monitoring import record_api_usage

SOURCE_TYPE_SENT_EMAIL = "sent_email"
SOURCE_TYPE_REPLY = "reply"
SOURCE_TYPE_NOTE = "note"


class MemoryServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _embedding_to_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def embed_text(text_value: str) -> list[float]:
    cleaned = _normalize_text(text_value)
    if not cleaned:
        raise MemoryServiceError("Text is required to create an embedding.", status_code=400)
    if not settings.openai_api_key:
        raise MemoryServiceError("OPENAI_API_KEY is not configured.", status_code=500)

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise MemoryServiceError(
            "OpenAI SDK is not installed. Run `pip install -r requirements.txt`.",
            status_code=500,
        ) from exc

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            input=cleaned,
        )
    except Exception as exc:
        raise MemoryServiceError(
            f"OpenAI embedding request failed for model `{settings.openai_embedding_model}`: {exc}",
            status_code=502,
        ) from exc

    try:
        return [float(value) for value in response.data[0].embedding]
    except Exception as exc:
        raise MemoryServiceError(
            "OpenAI did not return a valid embedding vector.",
            status_code=502,
        ) from exc


def _upsert_memory(
    db: Session,
    *,
    workspace_id: str,
    lead_id: str,
    source_type: str,
    source_id: str,
    content: str,
    created_at: datetime,
    allow_embedding_failure: bool = True,
) -> ConversationMemory:
    cleaned_content = content.strip()[:10000]
    if not cleaned_content:
        raise MemoryServiceError("Memory content cannot be empty.", status_code=400)

    memory = (
        db.query(ConversationMemory)
        .filter(
            ConversationMemory.source_type == source_type,
            ConversationMemory.source_id == source_id,
        )
        .first()
    )

    embedding = None
    try:
        embedding = embed_text(cleaned_content)
    except MemoryServiceError:
        record_api_usage(
            db,
            workspace_id=workspace_id,
            provider="openai",
            feature="memory_indexing",
            model_name=settings.openai_embedding_model,
            success=False,
            metadata={"source_type": source_type, "source_id": source_id},
        )
        if not allow_embedding_failure:
            raise
    else:
        record_api_usage(
            db,
            workspace_id=workspace_id,
            provider="openai",
            feature="memory_indexing",
            model_name=settings.openai_embedding_model,
            success=True,
            metadata={"source_type": source_type, "source_id": source_id},
        )

    if memory:
        memory.workspace_id = workspace_id
        memory.lead_id = lead_id
        memory.content = cleaned_content
        if embedding is not None:
            memory.embedding = embedding
        memory.created_at = created_at
        db.flush()
        return memory

    memory = ConversationMemory(
        workspace_id=workspace_id,
        lead_id=lead_id,
        source_type=source_type,
        source_id=source_id,
        content=cleaned_content,
        embedding=embedding,
        created_at=created_at,
    )
    db.add(memory)
    db.flush()
    return memory


def sync_sent_email_memory(
    db: Session, workspace_id: str, sent_email: SentEmail
) -> ConversationMemory:
    body = sent_email.email_body or ""
    subject = sent_email.email_subject or ""
    content = f"Sent email\nSubject: {subject}\nBody: {body}".strip()
    return _upsert_memory(
        db,
        workspace_id=workspace_id,
        lead_id=sent_email.lead_id,
        source_type=SOURCE_TYPE_SENT_EMAIL,
        source_id=sent_email.id,
        content=content,
        created_at=sent_email.sent_at,
    )


def sync_reply_memory(
    db: Session, workspace_id: str, email_reply: EmailReply
) -> ConversationMemory:
    content = f"Lead reply\nBody: {email_reply.reply_body}".strip()
    return _upsert_memory(
        db,
        workspace_id=workspace_id,
        lead_id=email_reply.lead_id,
        source_type=SOURCE_TYPE_REPLY,
        source_id=email_reply.id,
        content=content,
        created_at=email_reply.received_at,
    )


def sync_note_memory(db: Session, workspace_id: str, note: Note) -> ConversationMemory:
    content = f"Internal note\nBody: {note.content}".strip()
    return _upsert_memory(
        db,
        workspace_id=workspace_id,
        lead_id=note.lead_id,
        source_type=SOURCE_TYPE_NOTE,
        source_id=note.id,
        content=content,
        created_at=note.created_at,
    )


def search_memories(
    db: Session,
    *,
    workspace_id: str,
    query: str,
    lead_id: str | None = None,
    limit: int = 5,
) -> list[tuple[ConversationMemory, float]]:
    cleaned_query = _normalize_text(query)
    if not cleaned_query:
        raise MemoryServiceError("Query is required.", status_code=400)

    limit = max(1, min(limit, 20))
    query_embedding: list[float] | None = None
    try:
        query_embedding = embed_text(cleaned_query)
    except MemoryServiceError:
        record_api_usage(
            db,
            workspace_id=workspace_id,
            provider="openai",
            feature="memory_search_embedding",
            model_name=settings.openai_embedding_model,
            success=False,
            metadata={"lead_id": lead_id},
        )
        query_embedding = None
    else:
        record_api_usage(
            db,
            workspace_id=workspace_id,
            provider="openai",
            feature="memory_search_embedding",
            model_name=settings.openai_embedding_model,
            success=True,
            metadata={"lead_id": lead_id},
        )

    if query_embedding is not None and db.bind and db.bind.dialect.name == "postgresql":
        sql = text(
            """
            SELECT id, 1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM conversation_memories
            WHERE workspace_id = :workspace_id
              AND (:lead_id IS NULL OR lead_id = :lead_id)
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        )
        rows = db.execute(
            sql,
            {
                "embedding": _embedding_to_literal(query_embedding),
                "workspace_id": workspace_id,
                "lead_id": lead_id,
                "limit": limit,
            },
        ).all()

        ids_in_order = [row.id for row in rows]
        score_map = {row.id: float(row.score or 0.0) for row in rows}
        if not ids_in_order:
            return []

        memories = (
            db.query(ConversationMemory)
            .filter(ConversationMemory.id.in_(ids_in_order))
            .all()
        )
        memory_map = {memory.id: memory for memory in memories}
        return [
            (memory_map[memory_id], score_map[memory_id])
            for memory_id in ids_in_order
            if memory_id in memory_map
        ]

    memories = db.query(ConversationMemory).filter(
        ConversationMemory.workspace_id == workspace_id
    )
    if lead_id:
        memories = memories.filter(ConversationMemory.lead_id == lead_id)
    candidates = memories.all()

    if query_embedding is not None:
        scored = []
        for memory in candidates:
            if not memory.embedding:
                continue
            score = _cosine_similarity(query_embedding, memory.embedding)
            scored.append((memory, score))
        scored.sort(key=lambda item: (item[1], item[0].created_at), reverse=True)
        return scored[:limit]

    query_lower = cleaned_query.lower()
    scored = []
    for memory in candidates:
        content_lower = memory.content.lower()
        if query_lower not in content_lower:
            continue
        score = 1.0 if query_lower in content_lower else 0.0
        scored.append((memory, score))
    scored.sort(key=lambda item: (item[1], item[0].created_at), reverse=True)
    return scored[:limit]
