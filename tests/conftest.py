from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.database import Base
from app.db.models import Concept
from app.db.repositories import KnowledgeRepository
from app.main import create_app


class FakeLLM:
    """Scriptable LLM provider for tests: canned text replies and per-schema structured results."""

    def __init__(
        self, text_replies: list[str] | None = None, structured: dict | None = None
    ) -> None:
        self.text_replies = list(text_replies or [])
        self.structured = structured or {}
        self.calls: list[tuple] = []

    def generate(self, messages, *, max_tokens: int = 1024, temperature: float = 0.3) -> str:
        self.calls.append(("generate", messages))
        if self.text_replies:
            return self.text_replies.pop(0)
        return "A canned explanation from the fake LLM."

    def structured_generate(
        self,
        messages,
        *,
        schema,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        retries: int = 1,
    ):
        self.calls.append(("structured_generate", schema))
        handler = self.structured.get(schema)
        if handler is None:
            raise AssertionError(f"FakeLLM has no handler for {schema.__name__}")
        return handler(messages) if callable(handler) else handler


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=tmp_path / "data" / "uploads",
        mastery_min_evidence=1,
    )


@pytest.fixture()
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture()
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture()
def llm_client(settings: Settings, fake_llm: FakeLLM) -> TestClient:
    with TestClient(create_app(settings, llm=fake_llm)) as test_client:
        yield test_client


@pytest.fixture()
def session_factory(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'unit.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def seed(session_factory):
    def _seed(names: list[str], edges: list[tuple[str, str]] | None = None) -> dict[str, Concept]:
        with session_factory() as session:
            repository = KnowledgeRepository(session)
            concepts = {
                name: repository.create_concept(name=name, description=f"About {name}.")
                for name in names
            }
            for source, target in edges or []:
                repository.create_relationship(
                    source_concept_id=concepts[source].id,
                    target_concept_id=concepts[target].id,
                    relation_type="PREREQUISITE_OF",
                    confidence=0.8,
                )
            session.commit()
        return concepts

    return _seed
