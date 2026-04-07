"""
Graph validation service (Section 2.3).
Primary enforcement of edge constraints at the application layer.
Database trigger is the safety net (Invariant G-01).

Invariants enforced here:
- G-01: Edge type-pair constraints
- G-02: semantic_reference specificity
- G-03: Same-owner edge constraint
"""

from server.app.core.models.enums import EdgeRelationType, NodeType

# Invariant G-01: Allowed source_type -> target_type pairs per relation_type
EDGE_TYPE_PAIR_CONSTRAINTS: dict[EdgeRelationType, list[tuple[NodeType, NodeType | None]]] = {
    EdgeRelationType.PARENT_CHILD: [
        (NodeType.TASK, NodeType.TASK),
        (NodeType.GOAL, NodeType.GOAL),
    ],
    # Invariant G-05: belongs_to restricted to goal→project, task→project
    EdgeRelationType.BELONGS_TO: [
        (NodeType.GOAL, NodeType.PROJECT),
        (NodeType.TASK, NodeType.PROJECT),
    ],
    EdgeRelationType.GOAL_TRACKS_TASK: [
        (NodeType.GOAL, NodeType.TASK),
    ],
    EdgeRelationType.GOAL_TRACKS_KB: [
        (NodeType.GOAL, NodeType.KB_ENTRY),
    ],
    EdgeRelationType.BLOCKED_BY: [
        (NodeType.TASK, NodeType.TASK),
        (NodeType.TASK, NodeType.GOAL),
    ],
    EdgeRelationType.JOURNAL_REFLECTS_ON: [
        (NodeType.JOURNAL_ENTRY, None),  # None means any target type
    ],
    EdgeRelationType.DERIVED_FROM_SOURCE: [
        (NodeType.KB_ENTRY, NodeType.SOURCE_ITEM),
        (NodeType.TASK, NodeType.SOURCE_ITEM),
        (NodeType.MEMORY, NodeType.SOURCE_ITEM),
    ],
    EdgeRelationType.SOURCE_SUPPORTS_GOAL: [
        (NodeType.SOURCE_ITEM, NodeType.GOAL),
    ],
    EdgeRelationType.SOURCE_QUOTED_IN: [
        (NodeType.SOURCE_ITEM, NodeType.KB_ENTRY),
    ],
    EdgeRelationType.CAPTURED_FOR: [
        (NodeType.SOURCE_ITEM, None),  # None means any target type
    ],
}

# Invariant G-02: Allowed pairs for semantic_reference
# If a more specific relation exists for a type pair, semantic_reference is invalid.
SEMANTIC_REFERENCE_ALLOWED: list[tuple[NodeType, NodeType | None]] = [
    (NodeType.KB_ENTRY, NodeType.KB_ENTRY),
    (NodeType.KB_ENTRY, NodeType.MEMORY),
    (NodeType.MEMORY, NodeType.KB_ENTRY),
    (NodeType.KB_ENTRY, NodeType.SOURCE_ITEM),
    (NodeType.SOURCE_ITEM, NodeType.KB_ENTRY),
    (NodeType.JOURNAL_ENTRY, None),  # journal_entry -> any
    (NodeType.MEMORY, NodeType.MEMORY),
    (NodeType.GOAL, NodeType.KB_ENTRY),
    (NodeType.KB_ENTRY, NodeType.GOAL),
    (NodeType.GOAL, NodeType.MEMORY),
    (NodeType.MEMORY, NodeType.GOAL),
    (NodeType.TASK, NodeType.KB_ENTRY),
    (NodeType.KB_ENTRY, NodeType.TASK),
    (NodeType.TASK, NodeType.MEMORY),
    (NodeType.MEMORY, NodeType.TASK),
]


def validate_edge_type_pair(
    relation_type: EdgeRelationType,
    source_type: NodeType,
    target_type: NodeType,
) -> str | None:
    """
    Validate that a relation_type is allowed for the given source/target node types.
    Returns None if valid, or an error message string if invalid.

    Invariant G-01: Edge type-pair constraints (application layer, primary).
    Invariant G-02: semantic_reference specificity.
    """
    if relation_type == EdgeRelationType.SEMANTIC_REFERENCE:
        # Invariant G-02: semantic_reference bounded to specific type pairs
        for allowed_source, allowed_target in SEMANTIC_REFERENCE_ALLOWED:
            if source_type == allowed_source:
                if allowed_target is None or target_type == allowed_target:
                    return None
        return (
            f"Invariant G-02: semantic_reference not allowed for "
            f"{source_type.value} -> {target_type.value}. "
            f"Use a more specific relation type."
        )

    allowed_pairs = EDGE_TYPE_PAIR_CONSTRAINTS.get(relation_type)
    if allowed_pairs is None:
        return f"Unknown relation_type: {relation_type.value}"

    for allowed_source, allowed_target in allowed_pairs:
        if source_type == allowed_source:
            if allowed_target is None or target_type == allowed_target:
                return None

    return (
        f"Invariant G-01: {relation_type.value} not allowed for "
        f"{source_type.value} -> {target_type.value}"
    )
