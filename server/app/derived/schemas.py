"""
DerivedExplanation schema type (Section 4.11).
Formal shared schema type required for all user-facing Derived outputs.

Invariant D-01: Every Derived output that surfaces to the user must include
a valid DerivedExplanation with at minimum summary (human-readable) and
factors[] (structured reasons). Internal-only computations may omit it.

This type is defined once in code and documentation. Services may add
optional fields for service-specific detail but must not omit the
required core fields.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DerivedFactor:
    """
    A single contributing factor in a DerivedExplanation.
    Section 4.11, Table 37: { signal, value, weight }
    """
    signal: str        # Name of the contributing signal (e.g., "days_untouched")
    value: Any         # The actual value (e.g., 14)
    weight: float      # How much this factor contributed (0.0-1.0)


@dataclass
class DerivedExplanation:
    """
    Section 4.11: DerivedExplanation schema type.
    Invariant D-01: Required for all user-facing Derived outputs.

    Fields (Table 37):
    - summary (TEXT, required): Human-readable explanation
    - factors (JSONB[], required): Array of {signal, value, weight}
    - confidence (FLOAT NULL, optional): Overall confidence (0.0-1.0)
    - generated_at (TIMESTAMPTZ NULL, optional): When computed
    - version (TEXT NULL, optional): Schema or prompt version
    """
    # Required fields
    summary: str
    factors: list[DerivedFactor]

    # Optional fields
    confidence: float | None = None
    generated_at: datetime | None = None
    version: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dict for JSON responses."""
        result = {
            "summary": self.summary,
            "factors": [
                {"signal": f.signal, "value": f.value, "weight": f.weight}
                for f in self.factors
            ],
        }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.generated_at is not None:
            result["generated_at"] = self.generated_at.isoformat()
        if self.version is not None:
            result["version"] = self.version
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "DerivedExplanation":
        """Deserialize from dict."""
        factors = [
            DerivedFactor(signal=f["signal"], value=f["value"], weight=f["weight"])
            for f in data.get("factors", [])
        ]
        generated_at = None
        if data.get("generated_at"):
            generated_at = datetime.fromisoformat(data["generated_at"])
        return cls(
            summary=data["summary"],
            factors=factors,
            confidence=data.get("confidence"),
            generated_at=generated_at,
            version=data.get("version"),
        )

    @classmethod
    def validate(cls, explanation: "DerivedExplanation") -> None:
        """
        Validate that a DerivedExplanation meets Invariant D-01 requirements.
        Raises ValueError if invalid.
        """
        # Invariant D-01: summary and factors are required
        if not explanation.summary or not explanation.summary.strip():
            raise ValueError("Invariant D-01: DerivedExplanation.summary is required and must be non-empty")
        if not explanation.factors:
            raise ValueError("Invariant D-01: DerivedExplanation.factors must be a non-empty list")
        for f in explanation.factors:
            if not f.signal:
                raise ValueError("Invariant D-01: Each factor must have a non-empty signal name")
        if explanation.confidence is not None:
            if not (0.0 <= explanation.confidence <= 1.0):
                raise ValueError("DerivedExplanation.confidence must be between 0.0 and 1.0")
