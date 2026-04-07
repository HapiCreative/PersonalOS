# CLAUDE.md - PersonalOS

## Project Overview

PersonalOS is a personal knowledge and behavior management system. It uses a graph-based data model where all entities are **nodes** connected by **edges**, organized into domain-specific modules (inbox, tasks, journal, goals, KB, sources, memory, templates). The system includes derived intelligence (signal scores, progress tracking), behavioral features (today view, cleanup), and temporal tracking (daily plans, focus sessions).

## Tech Stack

- **Frontend**: React 18 + TypeScript, Vite, React Router DOM, Lucide icons
- **Backend**: Python FastAPI (async), SQLAlchemy 2.0 + asyncpg, Pydantic 2
- **Database**: PostgreSQL with pgvector extension (vector embeddings for semantic search)
- **Auth**: JWT (HS256, 24h expiry), bcrypt password hashing
- **Queue**: Redis + ARQ for async jobs
- **No tests, no CI/CD, no Docker** currently configured

## Repository Structure

```
PersonalOS/
├── client/                          # React frontend
│   ├── src/
│   │   ├── api/                     # HTTP client + endpoint definitions
│   │   ├── auth/                    # AuthContext, LoginPage, RegisterPage
│   │   ├── components/
│   │   │   ├── layout/              # AppShell, Rail, ListPane, DetailPane
│   │   │   ├── common/              # Shared components
│   │   │   ├── context/             # ContextLayer display
│   │   │   ├── derived/             # Signal/progress displays
│   │   │   └── edges/               # EdgeChips, BacklinksDisplay
│   │   ├── domains/                 # Feature modules (inbox, tasks, journal, etc.)
│   │   ├── types/                   # TypeScript interfaces (index.ts)
│   │   └── styles/                  # CSS
│   ├── package.json
│   ├── tsconfig.json                # Strict mode, @/* path alias
│   └── vite.config.ts               # Proxy /api -> localhost:8000
├── server/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry point
│   │   ├── config.py                # Pydantic Settings (POS_ env prefix)
│   │   ├── core/
│   │   │   ├── auth/                # JWT, dependencies, auth router
│   │   │   ├── db/                  # SQLAlchemy async engine + session
│   │   │   ├── models/              # ORM models (node.py, edge.py, enums.py, user.py)
│   │   │   ├── routers/             # nodes, edges, search
│   │   │   ├── schemas/             # Pydantic request/response models
│   │   │   └── services/            # node_service, edge_service, embedding, graph, search
│   │   ├── domains/                 # Domain routers + services (inbox, tasks, journal, etc.)
│   │   ├── behavioral/             # Today view, cleanup system
│   │   ├── temporal/               # Daily plans, focus sessions, snooze
│   │   └── derived/                # Signal scores, progress, retrieval, context layer
│   └── requirements.txt
├── migrations/                      # Raw SQL migration files (001-007)
├── implementation-plan.md           # Architecture roadmap
└── personal-os-architecture-v6.docx # Architecture document
```

## Development Setup

### Frontend
```bash
cd client
npm install
npm run dev          # Vite dev server on port 5173
npm run build        # TypeScript check + production build
```

### Backend
```bash
cd server
pip install -r requirements.txt
uvicorn server.app.main:app --reload --port 8000
```

### Environment Variables
All prefixed with `POS_` (loaded from `.env` file):
- `POS_DATABASE_URL` - PostgreSQL async connection string
- `POS_DATABASE_URL_SYNC` - PostgreSQL sync connection string
- `POS_SECRET_KEY` - JWT signing secret
- `POS_REDIS_URL` - Redis connection string
- `POS_CORS_ORIGINS` - Allowed CORS origins

### Database
- PostgreSQL with `pgvector` extension required
- Migrations are raw SQL files in `migrations/` (run manually, phases 001-007)
- UUID primary keys, JSONB fields, custom PostgreSQL ENUMs

## Architecture & Key Patterns

### Data Model
- **Nodes**: Generic `nodes` table with companion tables per type (`task_nodes`, `journal_nodes`, `kb_nodes`, etc.)
- **Edges**: Typed relationships between nodes (11 relation types in `EdgeRelationType` enum)
- **Ownership**: Every query filters by `owner_id` - never expose cross-user data
- **Vector embeddings**: Stored as `VECTOR(1536)` in nodes table for semantic search

### Backend Conventions
- **Domain-driven structure**: Each domain (tasks, journal, goals, etc.) has its own `router.py`, `schemas.py`, `service.py`
- **Dependency injection**: FastAPI `Depends()` for auth, DB sessions, current user
- **Fully async**: All DB operations use `AsyncSession`; never use sync calls
- **Pydantic schemas**: Separate Create/Update/Response schemas per domain
- **Invariant comments**: Business rules documented as `S-01`, `B-03`, etc. - preserve these
- **Router prefixes**: All routes under `/api/` (e.g., `/api/tasks`, `/api/inbox`)

### Frontend Conventions
- **Module pattern**: Each domain in `src/domains/<name>/` contains a main module component
- **Path alias**: Use `@/` to reference `src/` (e.g., `@/api/client`)
- **Auth**: Token stored in localStorage as `pos_token`; AuthContext provides `user`, `loading`, `logout`
- **No state library**: Uses React hooks (`useState`, `useEffect`, `useCallback`) with vanilla `fetch`
- **AppShell + Rail**: Navigation via sidebar rail; active module rendered via switch in `App.tsx`

### API Routes
| Prefix | Purpose |
|--------|---------|
| `/api/auth` | Register, login |
| `/api/nodes` | Generic node CRUD |
| `/api/edges` | Edge creation/deletion |
| `/api/search` | Full-text + semantic search |
| `/api/inbox` | Inbox items |
| `/api/tasks` | Tasks + state transitions |
| `/api/journal` | Journal entries |
| `/api/templates` | Creation templates |
| `/api/sources` | Source items + fragments |
| `/api/kb` | Knowledge base |
| `/api/memory` | Memory nodes |
| `/api/goals` | Goals with task tracking |
| `/api/today` | Today view (suggestions, commit, reflection) |
| `/api/cleanup` | Stale item cleanup |
| `/api/derived` | Signal scores, progress, retrieval, context |
| `/api/daily-plans` | Daily planning |
| `/api/focus-sessions` | Focus/pomodoro sessions |
| `/api/snooze` | Snooze records |
| `/api/health` | Health check |

## Key Enums & Domain Types

Node types: `kb_entry`, `task`, `journal_entry`, `goal`, `memory`, `source_item`, `inbox_item`, `project`

Task statuses: `todo` -> `in_progress` -> `done` | `cancelled`

Inbox statuses: `pending` -> `promoted` | `dismissed` | `merged` | `archived`

Goal statuses: `active` -> `completed` | `archived`

## Guidelines for AI Assistants

1. **Read before editing** - Always read relevant files before modifying them
2. **Preserve invariant comments** - Don't remove `S-01`, `B-03`, etc. annotations
3. **Maintain ownership filtering** - Every query must filter by `owner_id`
4. **Keep async** - Use `async/await` throughout the backend; never introduce sync DB calls
5. **Match existing patterns** - New domains should follow the same router/schema/service structure
6. **Type safety** - Keep TypeScript strict mode happy; match Pydantic schemas to TS interfaces
7. **No `.env` commits** - Environment files are gitignored; use `POS_` prefix for new env vars
8. **SQL migrations** - New schema changes go in a new numbered SQL file in `migrations/`
9. **Frontend modules** - New features should be self-contained in `src/domains/<name>/`
10. **API proxy** - Frontend dev server proxies `/api` to `localhost:8000`; don't hardcode backend URLs
