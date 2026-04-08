# CLAUDE.md — PersonalOS Development Guidelines

## Project Structure

PersonalOS follows a **domain-driven architecture**. Each domain lives under
`server/app/domains/<domain>/` with a standard layout:

```
server/app/domains/<domain>/
├── __init__.py      # Module docstring only
├── router.py        # FastAPI endpoints
├── service.py       # Business logic
├── schemas.py       # Pydantic request/response models
```

Database models live in `server/app/core/models/`.

## Finance Module File Size Guards

The finance module (`server/app/domains/finance/`) is the largest domain and
must be kept maintainable. **Do not add logic to an existing file if it would
push that file beyond 400 lines.** When a file approaches or exceeds this
threshold, split it into focused sub-modules.

### Splitting rules

When `service.py`, `router.py`, or `schemas.py` grows too large, break it into
a **sub-package** while keeping imports stable:

```
server/app/domains/finance/
├── __init__.py
├── router.py               # thin file: mounts sub-routers only
├── schemas/
│   ├── __init__.py          # re-exports all schema classes
│   ├── accounts.py
│   ├── categories.py
│   ├── transactions.py
│   ├── transfers.py
│   ├── allocations.py
│   ├── csv_import.py
│   └── balance.py
├── services/
│   ├── __init__.py          # re-exports all public functions
│   ├── accounts.py          # create, get, list, update, deactivate
│   ├── categories.py        # CRUD, seed, tree
│   ├── allocations.py       # CRUD, validation
│   ├── transactions.py      # create, get, list, update, void
│   ├── transfers.py         # create, detect orphans, pair
│   ├── balance.py           # compute, reconcile, snapshots
│   └── csv_import.py        # parse, preview, execute, mappings
└── routers/
    ├── __init__.py           # re-exports the merged router
    ├── accounts.py
    ├── categories.py
    ├── transactions.py
    └── ...
```

### Mandatory checks before adding finance code

1. **Count lines first.** Before adding a function or endpoint to the finance
   module, check the target file's line count. If it is above 400 lines, split
   first, then add.
2. **One responsibility per file.** Each sub-module file should cover a single
   entity or workflow (accounts, categories, transactions, etc.). Do not mix
   unrelated concerns.
3. **Keep the public API stable.** Sub-package `__init__.py` files must
   re-export everything so that `from server.app.domains.finance.service import X`
   continues to work after a split.
4. **No god functions.** A single function should not exceed ~100 lines. If it
   does, extract helpers within the same sub-module file.
5. **Shared helpers go in a `_helpers.py`** inside the sub-package, not
   duplicated across files.

### Current state (as of April 2026)

| File         | Lines | Status     |
|--------------|-------|------------|
| `service.py` | ~1880 | **Needs split** — 40+ functions spanning 7 logical groups |
| `router.py`  | ~1020 | **Needs split** — 25+ endpoints |
| `schemas.py` | ~500  | Above threshold — split when next touched |

The logical sub-domains for splitting are: **accounts**, **categories**,
**allocations**, **transactions**, **transfers**, **balance/snapshots**, and
**csv_import**.

## General Coding Conventions

- **Design doc:** `finance-module-design-rev3.md` is the source of truth for
  finance module invariants (F-01 through F-13). Respect all invariants.
- **Async service functions** accept a `db: AsyncSession` as the first arg.
- **Router functions** use FastAPI dependency injection for the session.
- Follow the existing patterns in other domain modules when in doubt.
