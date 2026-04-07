"""
AI Modes service (Section 5.5 — Behavioral Layer).
Four AI modes: Ask, Plan, Reflect, Improve.

LLM responsibilities by layer enforced:
- Ask: factual_qa retrieval -> answer + citations -> ai_interaction_logs
- Plan: execution_qa retrieval -> suggested milestones/tasks -> promotes to Core on accept
- Reflect: reflection retrieval -> narrative + patterns -> derived (promotable)
- Improve: improvement retrieval -> prioritized recommendations -> ai_interaction_logs
"""

import json
import time
import uuid
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import AIMode
from server.app.core.services.llm import (
    get_llm_provider, is_llm_available, LLMResponse,
    ASK_SYSTEM_PROMPT, ASK_PROMPT_TEMPLATE,
    PLAN_SYSTEM_PROMPT, PLAN_PROMPT_TEMPLATE,
    REFLECT_SYSTEM_PROMPT, REFLECT_PROMPT_TEMPLATE,
    IMPROVE_SYSTEM_PROMPT, IMPROVE_PROMPT_TEMPLATE,
    PROMPT_VERSION,
)
from server.app.derived.retrieval_modes import retrieve, RetrievalResult
from server.app.temporal.ai_interaction_logs import log_interaction

logger = logging.getLogger(__name__)


@dataclass
class AIContext:
    """Context items retrieved for an AI mode interaction."""
    items: list[RetrievalResult] = field(default_factory=list)
    node_ids: list[uuid.UUID] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Format context items for LLM prompt injection."""
        parts = []
        for i, item in enumerate(self.items, 1):
            parts.append(
                f"[{i}] ({item.node_type}) {item.title}"
                f"{': ' + item.summary if item.summary else ''}"
                f" (relevance: {item.combined_score:.2f})"
            )
        return "\n".join(parts) if parts else "No relevant context found."


@dataclass
class AIModeResult:
    """Result from an AI mode interaction."""
    mode: str
    query: str
    response_text: str
    response_data: dict
    context: AIContext
    citations: list[dict] = field(default_factory=list)
    duration_ms: int = 0
    model_version: str = ""
    prompt_version: str = PROMPT_VERSION


# Retrieval mode mapping per AI mode (Section 5.5 + Section 4.4)
MODE_RETRIEVAL_MAP = {
    AIMode.ASK: "factual_qa",
    AIMode.PLAN: "execution_qa",
    AIMode.REFLECT: "reflection",
    AIMode.IMPROVE: "improvement",
}


async def _retrieve_context(
    db: AsyncSession,
    owner_id: uuid.UUID,
    mode: AIMode,
    query: str,
) -> AIContext:
    """Retrieve context using the appropriate retrieval mode for the AI mode."""
    retrieval_mode = MODE_RETRIEVAL_MAP.get(mode, "factual_qa")
    results = await retrieve(db, owner_id, retrieval_mode, query=query, limit=10)
    return AIContext(
        items=results,
        node_ids=[r.node_id for r in results],
    )


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw_text": text}


async def execute_ask(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
) -> AIModeResult:
    """
    Ask mode: factual_qa retrieval -> answer + citations -> ai_interaction_logs.
    Section 5.5: Factual Q&A with citations.
    """
    start = time.monotonic()
    context = await _retrieve_context(db, owner_id, AIMode.ASK, query)
    provider = get_llm_provider()

    if is_llm_available():
        prompt = ASK_PROMPT_TEMPLATE.format(
            context=context.to_context_string(),
            query=query,
        )
        llm_response = await provider.complete(prompt, system_prompt=ASK_SYSTEM_PROMPT)
        response_text = llm_response.text
        model_version = llm_response.model
    else:
        # Graceful degradation: return context items as the answer
        response_text = f"Found {len(context.items)} relevant items for your question."
        if context.items:
            response_text += "\n\nRelevant items:\n"
            for i, item in enumerate(context.items, 1):
                response_text += f"{i}. [{item.node_type}] {item.title}"
                if item.summary:
                    response_text += f" — {item.summary}"
                response_text += "\n"
        model_version = "noop"

    duration_ms = int((time.monotonic() - start) * 1000)

    # Build citations from context
    citations = [
        {"node_id": str(item.node_id), "title": item.title, "node_type": item.node_type}
        for item in context.items
    ]

    response_data = {"answer": response_text, "citations": citations}

    # Log interaction (Temporal)
    await log_interaction(
        db, owner_id, AIMode.ASK, query,
        response_summary=response_text[:500],
        response_data=response_data,
        context_node_ids=context.node_ids,
        duration_ms=duration_ms,
    )

    return AIModeResult(
        mode="ask",
        query=query,
        response_text=response_text,
        response_data=response_data,
        context=context,
        citations=citations,
        duration_ms=duration_ms,
        model_version=model_version,
    )


async def execute_plan(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
) -> AIModeResult:
    """
    Plan mode: execution_qa retrieval -> suggested milestones/tasks.
    Section 5.5: Promotes to Core on user accept (handled at API layer).
    """
    start = time.monotonic()
    context = await _retrieve_context(db, owner_id, AIMode.PLAN, query)
    provider = get_llm_provider()

    if is_llm_available():
        prompt = PLAN_PROMPT_TEMPLATE.format(
            context=context.to_context_string(),
            query=query,
        )
        llm_response = await provider.complete_json(prompt, system_prompt=PLAN_SYSTEM_PROMPT)
        response_data = llm_response if isinstance(llm_response, dict) else _parse_json_response(str(llm_response))
        model_version = provider.get_model_version()
    else:
        response_data = {
            "summary": f"Plan based on {len(context.items)} relevant items.",
            "milestones": [],
            "tasks": [],
            "recommendations": [item.title for item in context.items[:5]],
        }
        model_version = "noop"

    duration_ms = int((time.monotonic() - start) * 1000)
    response_text = response_data.get("summary", "Plan generated.")

    await log_interaction(
        db, owner_id, AIMode.PLAN, query,
        response_summary=response_text[:500],
        response_data=response_data,
        context_node_ids=context.node_ids,
        duration_ms=duration_ms,
    )

    return AIModeResult(
        mode="plan",
        query=query,
        response_text=response_text,
        response_data=response_data,
        context=context,
        duration_ms=duration_ms,
        model_version=model_version,
    )


async def execute_reflect(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
) -> AIModeResult:
    """
    Reflect mode: reflection retrieval -> narrative + patterns -> derived (promotable).
    Section 5.5: Output is Derived, user can promote to Core note/KB entry.
    """
    start = time.monotonic()
    context = await _retrieve_context(db, owner_id, AIMode.REFLECT, query)
    provider = get_llm_provider()

    if is_llm_available():
        prompt = REFLECT_PROMPT_TEMPLATE.format(
            context=context.to_context_string(),
            query=query,
        )
        llm_response = await provider.complete_json(prompt, system_prompt=REFLECT_SYSTEM_PROMPT)
        response_data = llm_response if isinstance(llm_response, dict) else _parse_json_response(str(llm_response))
        model_version = provider.get_model_version()
    else:
        response_data = {
            "narrative": f"Reflection based on {len(context.items)} recent items.",
            "patterns": [],
            "accomplishments": [item.title for item in context.items if item.node_type == "task"],
            "growth_areas": [],
            "insight": "Review your recent activity for patterns.",
        }
        model_version = "noop"

    duration_ms = int((time.monotonic() - start) * 1000)
    response_text = response_data.get("narrative", response_data.get("insight", "Reflection generated."))

    await log_interaction(
        db, owner_id, AIMode.REFLECT, query,
        response_summary=response_text[:500],
        response_data=response_data,
        context_node_ids=context.node_ids,
        duration_ms=duration_ms,
    )

    return AIModeResult(
        mode="reflect",
        query=query,
        response_text=response_text,
        response_data=response_data,
        context=context,
        duration_ms=duration_ms,
        model_version=model_version,
    )


async def execute_improve(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
) -> AIModeResult:
    """
    Improve mode: improvement retrieval -> prioritized recommendations.
    Section 5.5: Surfaces stale, blocked, and inefficient items.
    """
    start = time.monotonic()
    context = await _retrieve_context(db, owner_id, AIMode.IMPROVE, query)
    provider = get_llm_provider()

    if is_llm_available():
        prompt = IMPROVE_PROMPT_TEMPLATE.format(
            context=context.to_context_string(),
            query=query,
        )
        llm_response = await provider.complete_json(prompt, system_prompt=IMPROVE_SYSTEM_PROMPT)
        response_data = llm_response if isinstance(llm_response, dict) else _parse_json_response(str(llm_response))
        model_version = provider.get_model_version()
    else:
        response_data = {
            "summary": f"Improvement analysis of {len(context.items)} items.",
            "recommendations": [],
            "quick_wins": [],
            "items_to_archive": [],
        }
        model_version = "noop"

    duration_ms = int((time.monotonic() - start) * 1000)
    response_text = response_data.get("summary", "Improvement analysis complete.")

    await log_interaction(
        db, owner_id, AIMode.IMPROVE, query,
        response_summary=response_text[:500],
        response_data=response_data,
        context_node_ids=context.node_ids,
        duration_ms=duration_ms,
    )

    return AIModeResult(
        mode="improve",
        query=query,
        response_text=response_text,
        response_data=response_data,
        context=context,
        duration_ms=duration_ms,
        model_version=model_version,
    )


async def generate_briefing(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[str]:
    """
    Generate AI briefing for Today View (3-5 bullets).
    Section 5.1: Short, personalized, action-oriented.
    AI briefing should influence decisions, not just summarize data.
    """
    context = await _retrieve_context(db, owner_id, AIMode.ASK, "daily briefing overview")
    provider = get_llm_provider()

    if not is_llm_available():
        # Graceful degradation: generate simple bullets from context
        bullets = []
        task_count = sum(1 for i in context.items if i.node_type == "task")
        goal_count = sum(1 for i in context.items if i.node_type == "goal")
        if task_count > 0:
            bullets.append(f"You have {task_count} active tasks to review today.")
        if goal_count > 0:
            bullets.append(f"{goal_count} goals need attention.")
        if not bullets:
            bullets.append("Start your day by reviewing your goals and tasks.")
        return bullets[:5]

    from server.app.core.services.llm import BRIEFING_SYSTEM_PROMPT, BRIEFING_PROMPT_TEMPLATE
    prompt = BRIEFING_PROMPT_TEMPLATE.format(context=context.to_context_string())
    response = await provider.complete_json(prompt, system_prompt=BRIEFING_SYSTEM_PROMPT)
    if isinstance(response, dict) and "bullets" in response:
        return response["bullets"][:5]
    return ["Review your active tasks and goals for today."]
