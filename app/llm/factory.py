"""Build an LLMProvider from Settings, or return None when no provider is configured."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.openai_provider import OpenAICompatibleProvider
from app.llm.provider import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    if not settings.llm_enabled:
        return None
    assert settings.llm_base_url and settings.llm_api_key and settings.llm_model
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=settings.llm_model
    )
