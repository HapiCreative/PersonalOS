"""KB compilation pipeline (Section 7, 8.1).

6-stage pipeline: ingest -> parse -> compile -> review -> accept -> stale
"""

from sqlalchemy.ext.asyncio import AsyncSession

import uuid

from server.app.core.models.enums import CompileStatus, PipelineStage
from server.app.domains.kb.services.entries import get_kb_entry


# Valid compile_status transitions for the 6-stage pipeline
COMPILE_TRANSITIONS: dict[CompileStatus, set[CompileStatus]] = {
    CompileStatus.INGEST: {CompileStatus.PARSE},
    CompileStatus.PARSE: {CompileStatus.COMPILE},
    CompileStatus.COMPILE: {CompileStatus.REVIEW},
    CompileStatus.REVIEW: {CompileStatus.ACCEPT, CompileStatus.COMPILE},  # reject sends back to compile
    CompileStatus.ACCEPT: {CompileStatus.STALE},
    CompileStatus.STALE: {CompileStatus.INGEST},  # re-compile cycle
}


async def compile_kb_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    action: str,
) -> tuple:
    """
    Advance the KB compilation pipeline.

    Actions:
    - 'compile': Start compilation (ingest->parse->compile->review automatically)
    - 'accept': Accept a reviewed draft (review->accept)
    - 'reject': Send back for re-compilation (review->compile)

    The 6-stage pipeline: ingest -> parse -> compile -> review -> accept -> stale
    """
    pair = await get_kb_entry(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        raise ValueError("KB entry not found")

    node, kb = pair

    if action == "compile":
        # Fast-forward through ingest->parse->compile->review
        # In a full implementation, each stage would invoke LLM pipeline jobs.
        # For Phase 3, we simulate the pipeline progression.
        if kb.compile_status in (CompileStatus.INGEST, CompileStatus.STALE):
            kb.compile_status = CompileStatus.REVIEW
            kb.pipeline_stage = PipelineStage.REVIEW
            kb.compile_version += 1
        elif kb.compile_status == CompileStatus.COMPILE:
            kb.compile_status = CompileStatus.REVIEW
            kb.pipeline_stage = PipelineStage.REVIEW
        else:
            raise ValueError(
                f"Cannot compile from status {kb.compile_status.value}. "
                f"Expected ingest, stale, or compile."
            )

    elif action == "accept":
        if kb.compile_status != CompileStatus.REVIEW:
            raise ValueError(
                f"Cannot accept from status {kb.compile_status.value}. "
                f"Must be in review status."
            )
        kb.compile_status = CompileStatus.ACCEPT
        kb.pipeline_stage = PipelineStage.ACCEPTED

    elif action == "reject":
        if kb.compile_status != CompileStatus.REVIEW:
            raise ValueError(
                f"Cannot reject from status {kb.compile_status.value}. "
                f"Must be in review status."
            )
        kb.compile_status = CompileStatus.COMPILE
        kb.pipeline_stage = PipelineStage.DRAFT

    else:
        raise ValueError(f"Invalid action: {action}. Must be compile, accept, or reject.")

    await db.flush()
    return node, kb
