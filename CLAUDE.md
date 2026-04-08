# CLAUDE.md — PersonalOS Development Guidelines

## Project Structure

PersonalOS follows a **domain-driven architecture**. Each domain lives under
`server/app/domains/<domain>/` and uses **sub-packages by default** — never
generic monolithic files like `service.py` or `router.py`.

Database models live in `server/app/core/models/`.

### Default domain module structure

Every domain module **must** use this sub-package layout. Do not create generic
top-level `service.py`, `router.py`, or `schemas.py` files — split by entity
or workflow from the start:

```
server/app/domains/<domain>/
├── __init__.py
├── services/
│   ├── __init__.py           # re-exports all public functions
│   ├── <entity_a>.py         # one file per entity/workflow
│   ├── <entity_b>.py
│   └── _helpers.py           # shared internal helpers (if needed)
├── routers/
│   ├── __init__.py            # re-exports the merged router
│   ├── <entity_a>.py
│   └── <entity_b>.py
└── schemas/
    ├── __init__.py            # re-exports all schema classes
    ├── <entity_a>.py
    └── <entity_b>.py
```

**Keep the public API stable.** Sub-package `__init__.py` files must re-export
everything so that imports like
`from server.app.domains.<domain>.services import X` work from the package
level.

## Domain Module File Size Guards

These rules apply to **every** domain module under `server/app/domains/`.

### Mandatory checks before adding code to any domain

1. **No generic files.** Never put multiple entities or workflows into one
   file. Each `services/`, `routers/`, and `schemas/` file must cover a single
   entity or workflow.
2. **400-line hard limit per file.** Before adding a function or endpoint,
   check the target file's line count. If it would exceed 400 lines, break the
   file into smaller, more focused files first.
3. **No god functions.** A single function should not exceed ~100 lines. If it
   does, extract helpers within the same sub-module file.
4. **Shared helpers go in a `_helpers.py`** inside the sub-package, not
   duplicated across files.

### Legacy modules — migration needed

Existing domain modules still use the old generic-file pattern (`service.py`,
`router.py`, `schemas.py`). When any of these files are next touched, migrate
them to the sub-package structure above. **Do not add new code to a generic
file — migrate first, then add.**

**Finance** (most urgent):

| File         | Lines | Status     |
|--------------|-------|------------|
| `service.py` | ~1880 | **Needs migration** — 40+ functions spanning 7 logical groups |
| `router.py`  | ~1020 | **Needs migration** — 25+ endpoints |
| `schemas.py` | ~500  | **Needs migration** |

Target sub-packages for finance: **accounts**, **categories**,
**allocations**, **transactions**, **transfers**, **balance/snapshots**, and
**csv_import**.

## General Coding Conventions

- **Design doc:** `finance-module-design-rev3.md` is the source of truth for
  finance module invariants (F-01 through F-13). Respect all invariants.
- **Async service functions** accept a `db: AsyncSession` as the first arg.
- **Router functions** use FastAPI dependency injection for the session.
- Follow the existing patterns in other domain modules when in doubt.
