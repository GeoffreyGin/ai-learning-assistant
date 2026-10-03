"""Agent chat route (spec §20): the conversational entry point to the learning loop."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.schemas import AgentChatRequest, AgentChatResponse


def make_chat_router(controller) -> APIRouter:
    router = APIRouter(prefix="/agent", tags=["agent"])

    @router.post("/chat", response_model=AgentChatResponse)
    def chat(request: AgentChatRequest) -> AgentChatResponse:
        try:
            result = controller.chat(request.message)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        return AgentChatResponse.model_validate(result)

    return router
