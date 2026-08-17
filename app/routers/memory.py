from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.lead import Lead
from app.models.note import Note
from app.schemas.memory import (
    MemorySearchItem,
    MemorySearchRequest,
    MemorySearchResponse,
    NoteCreateRequest,
    NoteResponse,
)
from app.services.memory import MemoryServiceError, search_memories, sync_note_memory
from app.utils.auth import get_current_user

router = APIRouter()


@router.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreateRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteResponse:
    _, workspace = current

    lead = (
        db.query(Lead)
        .filter(Lead.id == payload.lead_id, Lead.workspace_id == workspace.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    note = Note(
        workspace_id=workspace.id,
        lead_id=lead.id,
        content=payload.content.strip(),
    )
    db.add(note)
    db.flush()

    try:
        sync_note_memory(db, workspace.id, note)
    except MemoryServiceError:
        pass

    db.commit()
    db.refresh(note)

    return NoteResponse(
        id=note.id,
        workspace_id=note.workspace_id,
        lead_id=note.lead_id,
        content=note.content,
        created_at=note.created_at,
    )


@router.post("/search", response_model=MemorySearchResponse)
def search_memory(
    payload: MemorySearchRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemorySearchResponse:
    _, workspace = current

    if payload.lead_id:
        lead = (
            db.query(Lead)
            .filter(Lead.id == payload.lead_id, Lead.workspace_id == workspace.id)
            .first()
        )
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found.")

    try:
        results = search_memories(
            db,
            workspace_id=workspace.id,
            lead_id=payload.lead_id,
            query=payload.query,
            limit=payload.limit,
        )
    except MemoryServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return MemorySearchResponse(
        items=[
            MemorySearchItem(
                id=memory.id,
                workspace_id=memory.workspace_id,
                lead_id=memory.lead_id,
                source_type=memory.source_type,
                source_id=memory.source_id,
                content=memory.content,
                score=score,
                created_at=memory.created_at,
            )
            for memory, score in results
        ]
    )
