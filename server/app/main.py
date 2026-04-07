"""
Personal OS — FastAPI Application Entry Point.
Section 8.1: FastAPI + Python, domain-driven structure.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.app.config import settings
from server.app.core.auth.router import router as auth_router
from server.app.core.routers.nodes import router as nodes_router
from server.app.core.routers.edges import router as edges_router
from server.app.core.routers.search import router as search_router
from server.app.domains.inbox.router import router as inbox_router
from server.app.domains.tasks.router import router as tasks_router, events_router
from server.app.domains.journal.router import router as journal_router
from server.app.domains.templates.router import router as templates_router

app = FastAPI(
    title="Personal OS",
    description="A behavior system for your life",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core routers
app.include_router(auth_router)
app.include_router(nodes_router)
app.include_router(edges_router)
app.include_router(search_router)

# Domain routers
app.include_router(inbox_router)
app.include_router(tasks_router)
app.include_router(journal_router)
app.include_router(templates_router)

# Temporal routers
app.include_router(events_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
