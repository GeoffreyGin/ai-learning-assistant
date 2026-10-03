"""LLM provider abstraction (spec §7). All LLM access goes through LLMProvider."""

from __future__ import annotations

from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMError(RuntimeError):
    """Transport or API-level failure from the LLM provider."""


class LLMOutputError(LLMError):
    """The LLM returned output that could not be validated against the requested schema."""


class LLMProvider(Protocol):
    def generate(
        self, messages: list[LLMMessage], *, max_tokens: int = 1024, temperature: float = 0.3
    ) -> str: ...

    def structured_generate(
        self,
        messages: list[LLMMessage],
        *,
        schema: type[SchemaT],
        max_tokens: int = 2048,
        temperature: float = 0.2,
        retries: int = 1,
    ) -> SchemaT: ...
