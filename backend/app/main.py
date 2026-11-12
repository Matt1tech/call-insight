from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import analytics, conversations, health
from app.core.config import get_settings
from app.repositories.analysis_repository import get_repository


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Call Insight Dashboard",
        description="Grocery assistance call analysis: classification, risk and actions.",
        version="0.1.0",
        docs_url="/docs",
    )

    get_repository()  # fail fast if the data files are invalid

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(conversations.router)
    api.include_router(analytics.router)
    app.include_router(api)
    app.include_router(health.router)  # GET /health at the root

    # Mounted last so API routes win over the static catch-all.
    if settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
