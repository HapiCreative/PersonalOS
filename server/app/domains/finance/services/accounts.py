"""Account service functions for the finance domain."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import AccountType, NodeType
from server.app.core.models.node import AccountNode, Node


async def create_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    account_type: AccountType,
    currency: str,
    summary: str | None = None,
    institution: str | None = None,
    account_number_masked: str | None = None,
    notes: str | None = None,
) -> tuple[Node, AccountNode]:
    """
    Create an account (Core node + account_nodes companion in single transaction).
    Section 2.1: Accounts are durable, user-owned entities.
    """
    node = Node(
        type=NodeType.ACCOUNT,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    account = AccountNode(
        node_id=node.id,
        account_type=account_type,
        institution=institution,
        currency=currency,
        account_number_masked=account_number_masked,
        is_active=True,
        notes=notes,
    )
    db.add(account)
    await db.flush()

    return node, account


async def get_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, AccountNode] | None:
    """Get an account by node ID, enforcing ownership."""
    stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, account = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, account


async def list_accounts(
    db: AsyncSession,
    owner_id: uuid.UUID,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, AccountNode]], int]:
    """List accounts with optional active/inactive filter, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.ACCOUNT]

    if is_active is not None:
        base_filter.append(AccountNode.is_active == is_active)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = ...,  # type: ignore[assignment]
    account_type: AccountType | None = None,
    institution: str | None = ...,  # type: ignore[assignment]
    currency: str | None = None,
    account_number_masked: str | None = ...,  # type: ignore[assignment]
    is_active: bool | None = None,
    notes: str | None = ...,  # type: ignore[assignment]
) -> tuple[Node, AccountNode] | None:
    """Update account fields, enforcing ownership."""
    pair = await get_account(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, account = pair

    if title is not None:
        node.title = title
    if summary is not ...:
        node.summary = summary
    if account_type is not None:
        account.account_type = account_type
    if institution is not ...:
        account.institution = institution
    if currency is not None:
        account.currency = currency
    if account_number_masked is not ...:
        account.account_number_masked = account_number_masked
    if is_active is not None:
        account.is_active = is_active
    if notes is not ...:
        account.notes = notes

    node.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return node, account


async def deactivate_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> tuple[Node, AccountNode] | None:
    """Soft deactivate an account (set is_active = false)."""
    pair = await get_account(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, account = pair
    account.is_active = False
    node.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return node, account
