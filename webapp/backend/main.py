"""FastAPI backend: serves the Mini App static build and the drawing-submission API."""
from __future__ import annotations

import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from webapp.backend.config import settings
from webapp.backend.routes.drawings import router as drawings_router
from webapp.backend.routes.leaderboard import router as leaderboard_router

app = FastAPI(title="Krivoy Telefon backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drawings_router)
app.include_router(leaderboard_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


_FRONTEND_DIST = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
