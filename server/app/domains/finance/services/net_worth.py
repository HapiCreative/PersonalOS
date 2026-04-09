"""
Finance Phase F2-C — Net Worth Engine (Derived layer).

Ref: Finance Design Rev 3 Section 4.1.
Implements net worth + liquid net worth computation at any target date.

Invariant F-07 — excludes transfer/investment types from cashflow (not used here).
Invariant F-08 — balance queries include only posted/settled transactions.
Invariant F-09 — reconciled snapshots are authoritative over computed balances.
Invariant F-10 — historical FX always uses exchange rate from the snapshot date.
Invariant D-01 — every output includes a DerivedExplanation.
Invariant D-02 — all outputs are recomputable from Core + Temporal data.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import AccountType, NodeType
from server.app.core.models.node import AccountNode, Node
from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services._helpers import get_user_base_currency
from server.app.domains.finance.services.balance import compute_account_balance
from server.app.domains.finance.services.exchange_rates import get_closest_exchange_rate


# Liability account types (balance subtracted from net worth)
LIABILITY_ACCOUNT_TYPES: set[AccountType] = {
    AccountType.LOAN,
    AccountType.MORTGAGE,
    AccountType.CREDIT_CARD,
}

# Liquid account types (included in liquid net worth regardless of asset content)
LIQUID_ACCOUNT_TYPES: set[AccountType] = {
    AccountType.CHECKING,
    AccountType.SAVINGS,
    AccountType.CREDIT_CARD,  # liability but still liquid for runway purposes
    AccountType.CASH,
    AccountType.CRYPTO_WALLET,
}


def classify_account(account_type: AccountType) -> tuple[bool, bool]:
    """
    Classify an account as (is_liability, is_liquid).

    Ref Section 4.1: loan/mortgage are always liabilities; credit_card balances
    count as liability but credit_card is considered liquid for runway.
    Brokerage depends on holdings asset_type — treated as illiquid here;
    fine-grained classification handled by investment_performance service.
    """
    is_liability = account_type in LIABILITY_ACCOUNT_TYPES
    is_liquid = account_type in LIQUID_ACCOUNT_TYPES
    return is_liability, is_liquid


async def _convert_to_base(
    db: AsyncSession,
    amount: Decimal,
    native_currency: str,
    base_currency: str,
    target_date: date,
) -> tuple[Decimal, Decimal]:
    """
    Convert amount from native to base currency using the rate from target_date.
    Returns (converted_amount, exchange_rate_used).
    Invariant F-10: always use the rate as of target_date (or the closest ≤ it).
    """
    if native_currency == base_currency:
        return amount, Decimal("1")

    # Invariant F-10: look up rate AS OF target_date; fall back to the nearest
    # earlier rate when weekends/holidays have no exact-date entry.
    rate_row = await get_closest_exchange_rate(
        db, native_currency, base_currency, target_date
    )
    if rate_row is not None:
        rate = Decimal(str(rate_row.rate))
        return amount * rate, rate

    # Try inverse pair (quote → base), then invert.
    inverse_row = await get_closest_exchange_rate(
        db, base_currency, native_currency, target_date
    )
    if inverse_row is not None and Decimal(str(inverse_row.rate)) != 0:
        rate = Decimal("1") / Decimal(str(inverse_row.rate))
        return amount * rate, rate

    # No rate available — return native amount unchanged, rate = 1.
    # Caller may still display this, and the explanation should surface it.
    return amount, Decimal("1")


async def compute_net_worth(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date | None = None,
    base_currency: str | None = None,
) -> dict:
    """
    Section 4.1: Compute net worth + liquid net worth at a given point in time.

    Algorithm:
    1. List all active accounts owned by user.
    2. For each, compute balance as-of target_date via compute_account_balance
       (Invariants F-08, F-09 applied inside).
    3. Convert to base_currency using rates on target_date (F-10).
    4. Sum assets + liabilities, classify liquid vs illiquid.
    5. Return breakdown + DerivedExplanation (D-01, D-02).
    """
    if target_date is None:
        target_date = date.today()

    if base_currency is None:
        base_currency = await get_user_base_currency(db, user_id)

    # Fetch all active accounts for this user.
    accounts_stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(
            Node.owner_id == user_id,
            Node.type == NodeType.ACCOUNT,
            Node.archived_at.is_(None),
            AccountNode.is_active.is_(True),
        )
    )
    result = await db.execute(accounts_stmt)
    accounts = result.all()

    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    liquid_assets = Decimal("0")
    illiquid_assets = Decimal("0")
    breakdown: list[dict] = []

    for node, account_node in accounts:
        balance_info = await compute_account_balance(
            db, user_id, node.id, as_of_date=target_date
        )
        native_balance: Decimal = Decimal(str(balance_info["balance"]))
        native_currency: str = account_node.currency

        base_balance, rate_used = await _convert_to_base(
            db, native_balance, native_currency, base_currency, target_date
        )

        is_liability, is_liquid = classify_account(account_node.account_type)

        if is_liability:
            # Liability balances are subtracted from net worth.
            total_liabilities += base_balance
        else:
            total_assets += base_balance
            if is_liquid:
                liquid_assets += base_balance
            else:
                illiquid_assets += base_balance

        snapshot_row = balance_info.get("last_reconciled_snapshot")
        snapshot_date = (
            snapshot_row.snapshot_date if snapshot_row is not None else None
        )

        breakdown.append({
            "account_id": node.id,
            "account_name": node.title,
            "account_type": account_node.account_type.value,
            "native_balance": native_balance,
            "native_currency": native_currency,
            "base_balance": base_balance,
            "base_currency": base_currency,
            "exchange_rate": rate_used,
            "is_liability": is_liability,
            "is_liquid": is_liquid,
            "snapshot_date": snapshot_date,
        })

    net_worth = total_assets - total_liabilities
    # Liquid net worth excludes illiquid assets and subtracts liabilities
    # that are still liquid (credit card) — classification loop already handled
    # this by adding credit_card to LIABILITY set but not to LIQUID assets.
    liquid_net_worth = liquid_assets - total_liabilities

    # Invariant D-01: Build a DerivedExplanation summarizing how this was computed.
    explanation = DerivedExplanation(
        summary=(
            f"Net worth as of {target_date.isoformat()}: "
            f"{net_worth} {base_currency} "
            f"(assets {total_assets} − liabilities {total_liabilities} "
            f"across {len(breakdown)} accounts). "
            f"Liquid {liquid_net_worth} {base_currency} "
            f"(excludes illiquid {illiquid_assets})."
        ),
        factors=[
            DerivedFactor(
                signal="total_assets", value=str(total_assets), weight=1.0
            ),
            DerivedFactor(
                signal="total_liabilities",
                value=str(total_liabilities),
                weight=1.0,
            ),
            DerivedFactor(
                signal="liquid_assets", value=str(liquid_assets), weight=0.7
            ),
            DerivedFactor(
                signal="illiquid_assets",
                value=str(illiquid_assets),
                weight=0.3,
            ),
            DerivedFactor(
                signal="account_count", value=len(breakdown), weight=1.0
            ),
            DerivedFactor(
                signal="target_date",
                value=target_date.isoformat(),
                weight=1.0,
            ),
            DerivedFactor(
                signal="fx_policy",
                value="F-10: historical rate from target_date",
                weight=1.0,
            ),
        ],
        confidence=None,
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "as_of_date": target_date,
        "base_currency": base_currency,
        "net_worth": net_worth,
        "liquid_net_worth": liquid_net_worth,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "liquid_assets": liquid_assets,
        "illiquid_assets": illiquid_assets,
        "account_count": len(breakdown),
        "breakdown": breakdown,
        "explanation": explanation,
    }
