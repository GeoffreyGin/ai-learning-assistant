from __future__ import annotations

from fastapi import FastAPI

from app.api.routes_documents import make_documents_router
from app.api.routes_knowledge import make_knowledge_router
from app.core.config import Settings
from app.db.database import Base, make_engine, make_session_factory, session_dependency
from app.ingestion.pipeline import IngestionService
from app.knowledge.extractor import LocalConceptExtractor


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    settings.ensure_directories()
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    get_session = session_dependency(make_session_factory(settings.database_url))
    ingestion_service = IngestionService(upload_dir=settings.upload_dir, extractor=LocalConceptExtractor())

    app = FastAPI(title="AI Personal Knowledge Engineer", version="0.1.0")
    app.include_router(make_documents_router(get_session, ingestion_service))
    app.include_router(make_knowledge_router(get_session))

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
