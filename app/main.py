from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent.controller import AgentController
from app.api.courses import install_courses
from app.api.routes_chat import make_chat_router
from app.api.routes_documents import make_documents_router
from app.api.routes_knowledge import make_graph_router, make_knowledge_router
from app.api.routes_learning import make_learning_router
from app.core.config import Settings
from app.db.database import Base, make_session_factory, session_dependency
from app.ingestion.pipeline import IngestionService
from app.knowledge.extractor import LocalConceptExtractor
from app.knowledge.llm_extractor import LLMConceptExtractor
from app.llm.factory import build_llm_provider
from app.llm.provider import LLMProvider


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    if llm is None:
        llm = build_llm_provider(settings)

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    description = "Look up document and concept IDs in the [live ID directory](/directory)."
    if (frontend_dist / "index.html").is_file():
        description += (
            "\n\n[Choose a document to summarize](/#/documents) · "
            "[Explore the visual graph and prerequisites by concept name](/#/graph)"
        )
    app = FastAPI(title="AI Personal Knowledge Engineer", version="0.1.0", description=description)
    def install_workspace(target: FastAPI, workspace: Settings):
        workspace.ensure_directories()
        sessions = make_session_factory(workspace.database_url)
        Base.metadata.create_all(sessions.kw["bind"])
        get_session = session_dependency(sessions)
        extractor = LLMConceptExtractor(llm) if llm is not None else LocalConceptExtractor()
        ingestion = IngestionService(
            upload_dir=workspace.upload_dir, extractor=extractor, llm=llm
        )
        target.include_router(make_documents_router(get_session, ingestion))
        target.include_router(make_knowledge_router(get_session, llm))
        target.include_router(make_graph_router(get_session, llm))
        target.include_router(make_learning_router(get_session, llm, workspace))
        target.include_router(make_chat_router(AgentController(sessions, llm, workspace)))
        return sessions

    sessions = install_workspace(app, settings)
    install_courses(app, settings, sessions, install_workspace)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Serve the built frontend (frontend/dist, produced by `npm run build`). The
    # catch-all returns index.html for any non-API path so client-side routes
    # (/chat, /graph, ...) work on refresh.
    if frontend_dist.is_dir():
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def frontend_index(full_path: str) -> FileResponse:
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
