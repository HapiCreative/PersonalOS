"""Shared helpers for finance intelligence router sub-modules."""

from server.app.domains.finance.schemas.derived import (
    DerivedExplanationResponse,
    DerivedFactorResponse,
)


def explanation_to_response(explanation) -> DerivedExplanationResponse:
    """Invariant D-01: serialize a DerivedExplanation for the API layer."""
    return DerivedExplanationResponse(
        summary=explanation.summary,
        factors=[
            DerivedFactorResponse(
                signal=f.signal, value=f.value, weight=f.weight
            )
            for f in explanation.factors
        ],
        confidence=explanation.confidence,
        generated_at=(
            explanation.generated_at.isoformat()
            if explanation.generated_at is not None
            else None
        ),
        version=explanation.version,
    )
