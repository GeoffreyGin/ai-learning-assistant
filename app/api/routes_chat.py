"""Agent chat route (spec §20): the conversational entry point to the learning loop."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas import AgentChatRequest, AgentChatResponse, AgentLogEntryResponse

_LOG_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) \[([^\]]+)\] (.*)$")


def make_chat_router(controller) -> APIRouter:
    router = APIRouter(prefix="/agent", tags=["agent"])

    @router.post("/chat", response_model=AgentChatResponse)
    def chat(request: AgentChatRequest) -> AgentChatResponse:
        try:
            result = controller.chat(**request.model_dump())
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        return AgentChatResponse.model_validate(result)

    @router.get("/history")
    def history():
        return controller.history()

    @router.get("/log", response_model=list[AgentLogEntryResponse])
    def agent_log(
        limit: int = Query(default=200, ge=1, le=2000),
    ) -> list[AgentLogEntryResponse]:
        """Last `limit` action-log lines from data/agent.log, newest first (spec §24)."""
        log_path = controller.settings.data_dir / "agent.log"
        if not log_path.is_file():
            return []
        entries: list[AgentLogEntryResponse] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            match = _LOG_LINE.match(line)
            if match:
                entries.append(
                    AgentLogEntryResponse(
                        timestamp=match.group(1), tool=match.group(2), detail=match.group(3)
                    )
                )
        return list(reversed(entries[-limit:]))

    return router
