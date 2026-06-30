"""FastAPI entry point for the Agent project.

This API runs alongside Streamlit. It does not replace the existing web app.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent.tools.agent_tools import REGISTERED_TOOL_DESCRIPTIONS
from api.routes.business import router as business_router
from services import get_chat_service
from services.diagnostics_service import build_agent_diagnostics


app = FastAPI(
    title="智扫通机器人智能客服 API",
    version="0.1.0",
    description="Lightweight FastAPI entry point for the existing Streamlit/ReactAgent project.",
)

app.include_router(business_router)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入")
    user_id: str | None = Field(default=None, description="可选用户ID")
    session_id: str | None = Field(default=None, description="可选会话ID")
    history: list[dict[str, str]] | None = Field(default=None, description="可选历史消息")
    session_memory: dict[str, Any] | None = Field(default=None, description="可选会话记忆")


class ChatResponse(BaseModel):
    response: str
    user_id: str | None = None
    session_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/diagnostics")
def diagnostics() -> dict[str, Any]:
    return build_agent_diagnostics(REGISTERED_TOOL_DESCRIPTIONS)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    response = get_chat_service().chat_once(
        request.message,
        user_id=request.user_id,
        session_id=request.session_id,
        history=request.history,
        session_memory=request.session_memory,
    )
    return ChatResponse(
        response=response,
        user_id=request.user_id,
        session_id=request.session_id,
    )
