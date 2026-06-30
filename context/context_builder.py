"""Lightweight context construction helpers for ChatService."""

from __future__ import annotations

from typing import Any


MAX_CONTEXT_MESSAGES = 10


def build_context_messages(
    history: list[dict[str, str]] | None,
    max_messages: int = MAX_CONTEXT_MESSAGES,
) -> list[dict[str, str]]:
    """Normalize and trim recent session history for the model."""

    if not history:
        return []

    normalized_messages = []
    for message in history[-max_messages:]:
        role = message.get("role")
        content = message.get("content")
        if not content:
            continue
        if role == "ai":
            role = "assistant"
        if role not in ["user", "assistant"]:
            continue
        normalized_messages.append({"role": role, "content": content})

    return normalized_messages


def build_user_id_context(user_id: str) -> str:
    return (
        f"当前会话默认用户ID：{user_id}。\n"
        "如果用户本轮问题中明确指定了其他用户ID，优先使用用户明确指定的ID；"
        "否则涉及设备、耗材、清扫历史、报告等用户数据工具时使用当前默认用户ID。"
    )


def build_planning_context(message: str) -> str:
    try:
        from planning.simple_planner import build_planning_context as build_plan

        return build_plan(message)
    except Exception:
        return (
            "轻量规划结果：\n"
            "- 任务类型：知识问答类\n"
            "- 推荐工具顺序：rag_summarize\n"
            "- 总结重点：专业知识, 操作建议\n"
            "- 兜底策略：如果规划模块不可用，按用户问题选择最相关工具，并在资料不足时说明。"
        )


def build_memory_context(
    message: str,
    user_id: str,
    session_memory: dict[str, Any] | None = None,
) -> str:
    """Build memory context and update session memory when available."""

    try:
        from memory.local_memory import (
            LocalMemoryStore,
            extract_memory_from_message,
            extract_memory_from_profile,
            format_memory_context,
            merge_memory_for_context,
        )

        store = LocalMemoryStore()
        persisted_memory = store.read_user_memory(user_id)
        profile_memory = extract_memory_from_profile(user_id)
        message_memory = extract_memory_from_message(message, user_id)

        base_memory = merge_memory_for_context({**profile_memory, **persisted_memory}, session_memory)
        merged_memory = {**base_memory, **message_memory}
        file_memory = store.update_user_memory(user_id, merged_memory)
        merged_memory = merge_memory_for_context(file_memory, merged_memory)

        if session_memory is not None:
            session_memory.clear()
            session_memory.update(merged_memory)
        return format_memory_context(merged_memory)
    except Exception:
        return "当前用户记忆：记忆读取失败，本轮将不使用记忆信息。"


def build_user_context_message(
    message: str,
    user_id: str,
    memory_context: str = "",
    planning_context: str | None = None,
) -> str:
    plan_context = planning_context if planning_context is not None else build_planning_context(message)
    return (
        f"{build_user_id_context(user_id)}\n"
        f"{memory_context}\n"
        f"{plan_context}\n"
        f"用户问题：{message}"
    )


def build_context_debug_summary(
    *,
    user_id: str,
    history: list[dict[str, str]] | None = None,
    session_memory: dict[str, Any] | None = None,
    message: str = "",
    max_messages: int = MAX_CONTEXT_MESSAGES,
) -> dict[str, Any]:
    """Return a safe, compact summary of context passed to the Agent.

    The summary intentionally avoids raw history, memory values, API keys, and
    any user-provided free text. It is meant for developer debugging only.
    """

    trimmed_messages = build_context_messages(history, max_messages)
    try:
        from planning.simple_planner import build_simple_plan

        task_type = build_simple_plan(message).task_type
    except Exception:
        task_type = "未知"

    return {
        "user_id": user_id,
        "history_message_count": len(trimmed_messages),
        "history_limit": max_messages,
        "has_memory": bool(session_memory),
        "memory_field_count": len(session_memory or {}),
        "planning_task_type": task_type,
    }
