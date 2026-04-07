"""
LLM service with flexible provider pattern (Section 7).
Phase 9: Full AI integration for 4 modes, enrichments, link suggestions.
Provider is configurable — not hardcoded to one vendor.

LLM responsibilities by layer enforced:
- Core support: compile drafts, extract fragments
- Derived support: summarize, rank, correlate, detect
- Behavioral support: generate briefings, classify, reflect
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standard response from LLM provider."""
    text: str
    model: str
    prompt_version: str
    tokens_used: int = 0
    metadata: dict | None = None


class LLMProvider(ABC):
    """Abstract base for LLM providers. Extend for OpenAI, Anthropic, local models, etc."""

    @abstractmethod
    async def complete(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 2000) -> LLMResponse:
        """Generate a completion from a prompt."""
        ...

    @abstractmethod
    async def complete_json(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 2000) -> dict:
        """Generate a JSON-structured completion."""
        ...

    @abstractmethod
    def get_model_version(self) -> str:
        """Return the model version string."""
        ...


class NoOpLLMProvider(LLMProvider):
    """
    No-op provider for when no LLM API key is configured.
    Returns sensible defaults so the system degrades gracefully.
    Rule 3: LLM enriches, never gates. Basic operations must work without AI.
    """

    async def complete(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 2000) -> LLMResponse:
        logger.warning("NoOpLLMProvider: No LLM configured. Returning empty response.")
        return LLMResponse(
            text="",
            model="noop",
            prompt_version="noop-v1",
            tokens_used=0,
        )

    async def complete_json(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 2000) -> dict:
        logger.warning("NoOpLLMProvider: No LLM configured. Returning empty dict.")
        return {}

    def get_model_version(self) -> str:
        return "noop"


# Global provider instance — set at startup or via configuration
_llm_provider: LLMProvider = NoOpLLMProvider()


def get_llm_provider() -> LLMProvider:
    """Get the current LLM provider."""
    return _llm_provider


def set_llm_provider(provider: LLMProvider) -> None:
    """Set the LLM provider (call at app startup)."""
    global _llm_provider
    _llm_provider = provider


def is_llm_available() -> bool:
    """Check if a real LLM provider is configured."""
    return not isinstance(_llm_provider, NoOpLLMProvider)


# =============================================================================
# Prompt templates for AI modes (Section 5.5)
# =============================================================================

PROMPT_VERSION = "v1.0"

ASK_SYSTEM_PROMPT = """You are a personal knowledge assistant. Answer the user's question using ONLY the provided context.
If the context doesn't contain enough information, say so clearly.
Always cite which sources informed your answer. Be concise and direct."""

ASK_PROMPT_TEMPLATE = """Context from knowledge base:
{context}

User question: {query}

Provide a factual answer with citations to the context items used."""

PLAN_SYSTEM_PROMPT = """You are a planning assistant. Help the user create actionable plans based on their goals, tasks, and knowledge.
Suggest concrete milestones and tasks. Be specific and time-aware."""

PLAN_PROMPT_TEMPLATE = """Current goals and tasks context:
{context}

User planning request: {query}

Suggest a structured plan with:
1. Milestones (if applicable)
2. Specific tasks to create
3. Priority recommendations
4. Timeline suggestions

Format as JSON with keys: summary, milestones (array of {{title, description}}), tasks (array of {{title, priority, due_suggestion}}), recommendations (array of strings)."""

REFLECT_SYSTEM_PROMPT = """You are a reflective thinking partner. Help the user find patterns, insights, and growth areas
from their journal entries, completed tasks, and behavioral history. Be thoughtful and honest."""

REFLECT_PROMPT_TEMPLATE = """Recent activity and journal context:
{context}

User reflection prompt: {query}

Provide a thoughtful reflection that:
1. Identifies patterns in recent activity
2. Highlights accomplishments
3. Notes areas for growth
4. Suggests one actionable insight

Format as JSON with keys: narrative (string), patterns (array of strings), accomplishments (array of strings), growth_areas (array of strings), insight (string)."""

IMPROVE_SYSTEM_PROMPT = """You are a productivity improvement advisor. Analyze the user's workflow and suggest specific improvements.
Focus on stale items, blocked progress, and efficiency gains. Be direct and actionable."""

IMPROVE_PROMPT_TEMPLATE = """Current state of tasks, goals, and content:
{context}

User improvement request: {query}

Provide prioritized recommendations:
1. Immediate actions (quick wins)
2. Process improvements
3. Items to archive or eliminate

Format as JSON with keys: summary (string), recommendations (array of {{title, description, priority, category}}), quick_wins (array of strings), items_to_archive (array of {{node_id, title, reason}})."""

LINK_SUGGESTION_SYSTEM_PROMPT = """You are analyzing content relationships. Given a source node and candidate target nodes,
identify which pairs have genuine semantic relationships. Be conservative — only suggest links with clear justification."""

LINK_SUGGESTION_PROMPT_TEMPLATE = """Source node:
Title: {source_title}
Type: {source_type}
Summary: {source_summary}

Candidate nodes for linking:
{candidates}

For each candidate that has a genuine relationship with the source, provide:
- The candidate's ID
- The relationship type (one of: semantic_reference, derived_from_source, source_supports_goal, captured_for)
- A confidence score (0.0-1.0)
- A clear rationale for why they're related

Format as JSON array of: {{target_node_id, relation_type, confidence, rationale}}
Only include genuinely related items. Empty array is fine if nothing is related."""

ENRICH_SOURCE_SYSTEM_PROMPT = """You are analyzing a source document. Extract key information faithfully and concisely."""

ENRICH_SOURCE_PROMPT_TEMPLATE = """Source content:
Title: {title}
Type: {source_type}
Content:
{content}

Provide:
1. A concise summary (2-3 sentences)
2. Key takeaways (3-5 bullet points)
3. Named entities (people, organizations, concepts, technologies)

Format as JSON with keys: summary (string), takeaways (array of strings), entities (array of {{name, type}})."""

KB_LINT_SYSTEM_PROMPT = """You are reviewing knowledge base entries for quality and freshness."""

KB_LINT_PROMPT_TEMPLATE = """KB Entry:
Title: {title}
Content: {content}
Last updated: {updated_at}
Compile status: {compile_status}

Evaluate:
1. Content quality (completeness, clarity, accuracy)
2. Staleness indicators
3. Suggested improvements

Format as JSON with keys: quality_score (0.0-1.0), is_stale (boolean), issues (array of strings), suggestions (array of strings)."""

CLASSIFY_INBOX_SYSTEM_PROMPT = """You are classifying inbox items. Determine what type of Core entity this should become."""

CLASSIFY_INBOX_PROMPT_TEMPLATE = """Inbox item:
Text: {raw_text}

Classify this item as one of:
- task: An actionable item to do
- kb_entry: Knowledge to preserve
- memory: A decision, insight, or lesson
- source_item: External content to process
- keep_inbox: Not clear enough to classify

Also extract:
- Suggested title
- Priority (if task): low, medium, high, urgent
- Memory type (if memory): decision, insight, lesson, principle, preference

Format as JSON with keys: classification (string), title (string), priority (string|null), memory_type (string|null), confidence (0.0-1.0), rationale (string)."""

BRIEFING_SYSTEM_PROMPT = """You are generating a personalized daily briefing. Be concise and action-oriented.
Each bullet should influence a decision, not just summarize data."""

BRIEFING_PROMPT_TEMPLATE = """Today's context:
{context}

Generate 3-5 short, actionable briefing bullets that help the user prioritize their day.
Focus on: overdue items, goal progress, patterns from recent activity.

Format as JSON with key: bullets (array of strings)."""
