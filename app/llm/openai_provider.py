"""OpenAI-compatible chat-completions implementation (works with DeepSeek and similar providers)."""

from __future__ import annotations

import json
import re

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.provider import LLMError, LLMMessage, LLMOutputError


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 90.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout
        )

    def generate(
        self, messages: list[LLMMessage], *, max_tokens: int = 1024, temperature: float = 0.3
    ) -> str:
        return self._complete(self._payload(messages, max_tokens, temperature))

    def structured_generate(
        self,
        messages: list[LLMMessage],
        *,
        schema: type[BaseModel],
        max_tokens: int = 2048,
        temperature: float = 0.2,
        retries: int = 1,
    ) -> BaseModel:
        """Ask the LLM for JSON matching `schema`, validate it, and retry once on invalid output."""
        schema_hint = json.dumps(schema.model_json_schema())
        conversation = messages + [
            LLMMessage(
                role="user",
                content=f"Respond with only a JSON object matching this JSON schema: {schema_hint}",
            )
        ]
        attempt = 0
        while True:
            raw = self._complete(
                self._payload(conversation, max_tokens, temperature, json_mode=True)
            )
            try:
                return schema.model_validate(json.loads(self._strip_fences(raw)))
            except (ValidationError, json.JSONDecodeError) as error:
                if attempt >= retries:
                    raise LLMOutputError(
                        f"Invalid structured output after {attempt + 1} attempt(s): {error}"
                    ) from error
                attempt += 1
                conversation += [
                    LLMMessage(role="assistant", content=raw),
                    LLMMessage(
                        role="user",
                        content=(
                            f"That output was invalid ({error}). "
                            "Return only valid JSON matching the schema."
                        ),
                    ),
                ]

    def _payload(
        self,
        messages: list[LLMMessage],
        max_tokens: int,
        temperature: float,
        *,
        json_mode: bool = False,
    ) -> dict:
        instructions = (
            "Write all learner-facing prose in English, including explanations, "
            "summaries, questions and feedback. Preserve exact source quotations, "
            "identifiers, names and required schema values. Typeset math with LaTeX: "
            "use $...$ for inline math and $$...$$ on separate lines for display math."
        )
        conversation = [message.model_dump() for message in messages]
        if conversation and conversation[0]["role"] == "system":
            conversation[0]["content"] += "\n\n" + instructions
        else:
            conversation.insert(0, {"role": "system", "content": instructions})
        payload: dict = {
            "model": self.model,
            "messages": conversation,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _complete(self, payload: dict) -> str:
        try:
            response = self.client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise LLMError(f"LLM request failed: {error}") from error
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMError("Unexpected LLM response shape.") from error
        if not content:
            raise LLMError("LLM returned empty content.")
        return content

    @staticmethod
    def _strip_fences(raw: str) -> str:
        stripped = raw.strip()
        return re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.IGNORECASE)
