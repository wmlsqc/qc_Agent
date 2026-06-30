"""Stable chat service entry point.

This module intentionally keeps the first phase small: it wraps the existing
ReactAgent while leaving Streamlit and the current Agent implementation intact.
Future API, memory, context, and planning layers can depend on this service
instead of constructing the Agent directly.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from context.context_builder import (
    MAX_CONTEXT_MESSAGES,
    build_user_id_context,
    build_context_messages,
    build_context_debug_summary,
    build_memory_context,
    build_planning_context,
)


GREETING_RESPONSE = "你好，我是智扫通机器人智能客服，可以帮你查询设备状态、耗材寿命、清扫记录，也可以进行故障诊断。"
MODEL_ERROR_RESPONSE = "当前模型服务连接异常，请稍后重试。"
SOURCE_MARKERS = ["参考来源：", "参考来源:", "来源：", "来源:"]


class ChatService:
    """Application-level facade for chat interactions."""

    MAX_CONTEXT_MESSAGES = MAX_CONTEXT_MESSAGES

    def __init__(self, agent: Any | None = None):
        self._agent = agent
        self.last_context_debug_summary: dict[str, Any] = {
            "user_id": "未设置",
            "history_message_count": 0,
            "history_limit": self.MAX_CONTEXT_MESSAGES,
            "has_memory": False,
            "memory_field_count": 0,
            "planning_task_type": "未开始",
        }

    @property
    def agent(self) -> Any:
        if self._agent is None:
            from agent.react_agent import ReactAgent

            self._agent = ReactAgent()
        return self._agent

    def stream_chat(
        self,
        message: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        history: list[dict[str, str]] | None = None,
        session_memory: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """Stream an Agent response.

        `user_id` and `session_id` are accepted now so later phases can add
        memory and session isolation without changing callers.
        """

        _ = session_id
        resolved_user_id = self._resolve_user_id(message, user_id)
        memory_context = build_memory_context(message, resolved_user_id, session_memory)
        if self._is_greeting(message):
            self.last_context_debug_summary = {
                "user_id": resolved_user_id,
                "history_message_count": len(build_context_messages(history, self.MAX_CONTEXT_MESSAGES)),
                "history_limit": self.MAX_CONTEXT_MESSAGES,
                "has_memory": bool(session_memory),
                "memory_field_count": len(session_memory or {}),
                "planning_task_type": "寒暄类",
            }
            yield GREETING_RESPONSE
            return

        planning_context = build_planning_context(message)
        self.last_context_debug_summary = build_context_debug_summary(
            user_id=resolved_user_id,
            history=history,
            session_memory=session_memory,
            message=message,
            max_messages=self.MAX_CONTEXT_MESSAGES,
        )
        self._set_agent_current_user_id(resolved_user_id)
        hidden_context = self._build_hidden_context(
            user_id=resolved_user_id,
            memory_context=memory_context,
            planning_context=planning_context,
        )
        try:
            for chunk in self.agent.execute_stream(
                    message,
                    messages=build_context_messages(history, self.MAX_CONTEXT_MESSAGES),
                    hidden_context=hidden_context,
            ):
                cleaned_chunk = self._remove_source_markers(chunk)
                if cleaned_chunk:
                    yield cleaned_chunk
        except Exception:
            yield MODEL_ERROR_RESPONSE

    def chat_once(
        self,
        message: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        history: list[dict[str, str]] | None = None,
        session_memory: dict[str, Any] | None = None,
    ) -> str:
        """Return a complete Agent response as a single string."""

        return "".join(
            self.stream_chat(
                message,
                user_id=user_id,
                session_id=session_id,
                history=history,
                session_memory=session_memory,
            )
        ).strip()

    def _build_context_messages(
        self,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        return build_context_messages(history, self.MAX_CONTEXT_MESSAGES)

    def _resolve_user_id(self, message: str, default_user_id: str | None = None) -> str:
        explicit_user_id = self.extract_user_id(message)
        return explicit_user_id or default_user_id or "1001"

    @staticmethod
    def extract_user_id(message: str) -> str | None:
        patterns = [
            r"用户\s*ID\s*[:：]?\s*(\d{4,})",
            r"user[_\s-]?id\s*[:：]?\s*(\d{4,})",
            r"用户\s*(\d{4,})",
            r"我是\s*(\d{4,})",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _build_user_context_message(message: str, user_id: str, memory_context: str = "") -> str:
        return "\n".join(
            [
                build_user_id_context(user_id),
                memory_context,
                build_planning_context(message),
                "以上为内部上下文，仅供模型参考，不得在最终回答中复述。",
            ]
        )

    @staticmethod
    def _set_agent_current_user_id(user_id: str) -> None:
        try:
            from agent.tools.agent_tools import set_current_user_id

            set_current_user_id(user_id)
        except Exception:
            pass

    @staticmethod
    def _build_planning_context(message: str) -> str:
        return build_planning_context(message)

    @staticmethod
    def _build_hidden_context(
        *,
        user_id: str,
        memory_context: str,
        planning_context: str,
    ) -> str:
        return "\n".join(
            [
                "以下为内部上下文，只能用于理解用户需求和选择工具。",
                "禁止在最终回答中复述、展示或解释这些内部上下文。",
                "禁止输出“当前会话默认用户ID”“当前用户记忆”“轻量规划结果”“用户问题”等内部标签。",
                build_user_id_context(user_id),
                memory_context,
                planning_context,
            ]
        )

    @staticmethod
    def _is_greeting(message: str) -> bool:
        normalized_message = re.sub(r"[\s，。！!？?~～,.]", "", message or "").lower()
        return normalized_message in {
            "你好",
            "您好",
            "哈喽",
            "hello",
            "hi",
            "嗨",
            "在吗",
            "在不在",
        }

    @staticmethod
    def _remove_source_markers(text: str) -> str:
        cleaned_text = text or ""
        for marker in SOURCE_MARKERS:
            if marker in cleaned_text:
                cleaned_text = cleaned_text.split(marker, 1)[0]
        return cleaned_text

    def get_context_debug_summary(self) -> dict[str, Any]:
        return dict(self.last_context_debug_summary)

    def reset_context_debug_summary(
        self,
        user_id: str | None = None,
        session_memory: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> None:
        context_messages = build_context_messages(history, self.MAX_CONTEXT_MESSAGES)
        self.last_context_debug_summary = {
            "user_id": user_id or "未设置",
            "history_message_count": len(context_messages),
            "history_limit": self.MAX_CONTEXT_MESSAGES,
            "has_memory": bool(session_memory),
            "memory_field_count": len(session_memory or {}),
            "planning_task_type": "未开始",
        }

    @staticmethod
    def _prepare_memory_context(
        message: str,
        user_id: str,
        session_memory: dict[str, Any] | None = None,
    ) -> str:
        return build_memory_context(message, user_id, session_memory)


_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Return the process-wide chat service instance."""

    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
