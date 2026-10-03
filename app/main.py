from __future__ import annotations

from fastapi import FastAPI

from app.agent.controller import AgentController
from app.api.routes_chat import make_chat_router
from app.api.routes_documents import make_documents_router
from app.api.routes_knowledge import make_graph_router, make_knowledge_router
from app.api.routes_learning import make_learning_router
from app.core.config import Settings
from app.db.database import Base, make_engine, make_session_factory, session_dependency
from app.ingestion.pipeline import IngestionService
from app.knowledge.extractor import LocalConceptExtractor
from app.knowledge.llm_extractor import LLMConceptExtractor
from app.llm.factory import build_llm_provider
from app.llm.provider import LLMProvider


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    settings.ensure_directories()
    if llm is None:
        llm = build_llm_provider(settings)
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    get_session = session_dependency(make_session_factory(settings.database_url))
    extractor = LLMConceptExtractor(llm) if llm is not None else LocalConceptExtractor()
    ingestion_service = IngestionService(
        upload_dir=settings.upload_dir, extractor=extractor, llm=llm
    )

    app = FastAPI(title="AI Personal Knowledge Engineer", version="0.1.0")
    app.include_router(make_documents_router(get_session, ingestion_service))
    app.include_router(make_knowledge_router(get_session, llm))
    app.include_router(make_graph_router(get_session, llm))
    app.include_router(make_learning_router(get_session, llm, settings))
    app.include_router(
        make_chat_router(
            AgentController(make_session_factory(settings.database_url), llm, settings)
        )
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
