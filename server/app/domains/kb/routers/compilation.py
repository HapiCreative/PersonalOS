"""KB compilation pipeline endpoint (Section 8.3)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.kb.schemas import KBCompileRequest, KBCompileResponse
from server.app.domains.kb.services import compile_kb_entry

router = APIRouter()


@router.post("/{node_id}/compile", response_model=KBCompileResponse)
async def compile_kb_endpoint(
    node_id: uuid.UUID,
    body: KBCompileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger or advance the KB compilation pipeline.
    6-stage: ingest -> parse -> compile -> review -> accept -> stale
    """
    try:
        node, kb = await compile_kb_entry(db, user.id, node_id, body.action)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return KBCompileResponse(
        node_id=node.id,
        compile_status=kb.compile_status,
        pipeline_stage=kb.pipeline_stage,
        compile_version=kb.compile_version,
    )
