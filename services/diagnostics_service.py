"""Shared diagnostics service for Agent tools and FastAPI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from utils.config_handler import chroma_conf, rag_conf
from utils.path_tool import get_abs_path


CSV_FILES = [
    "data/external/users.csv",
    "data/external/devices.csv",
    "data/external/consumables.csv",
    "data/external/cleaning_history.csv",
    "data/external/records.csv",
]


def _has_dashscope_api_key() -> bool:
    if os.getenv("DASHSCOPE_API_KEY"):
        return True

    env_path = Path(get_abs_path(".env"))
    if not env_path.exists():
        return False

    try:
        with env_path.open("r", encoding="utf-8") as f:
            return any(
                line.strip().startswith("DASHSCOPE_API_KEY=")
                and bool(line.split("=", 1)[1].strip())
                for line in f
            )
    except Exception:
        return False


def build_agent_diagnostics(tool_descriptions: list[str] | None = None) -> dict[str, Any]:
    """Build a structured diagnostics result without exposing secret values."""

    csv_status = {
        path: Path(get_abs_path(path)).exists()
        for path in CSV_FILES
    }
    vector_path = get_abs_path(chroma_conf["persist_directory"])
    knowledge_path = get_abs_path(chroma_conf["data_path"])
    vector_exists = Path(vector_path).exists()
    knowledge_exists = Path(knowledge_path).exists()
    has_dashscope_key = _has_dashscope_api_key()
    missing_csv = [path for path, exists in csv_status.items() if not exists]
    overall_status = "正常" if not missing_csv and vector_exists and has_dashscope_key else "需检查"

    return {
        "overall_status": overall_status,
        "models": {
            "chat_model": rag_conf["chat_model_name"],
            "embedding_model": rag_conf["embedding_model_name"],
        },
        "tools": tool_descriptions or [],
        "csv_files": csv_status,
        "knowledge_base": {
            "path": knowledge_path,
            "exists": knowledge_exists,
        },
        "vector_store": {
            "path": vector_path,
            "exists": vector_exists,
        },
        "environment": {
            "DASHSCOPE_API_KEY": {
                "exists": has_dashscope_key,
            }
        },
        "notes": [
            "自检只显示 DASHSCOPE_API_KEY 是否存在，不返回密钥内容。",
        ],
    }


def format_agent_diagnostics(diagnostics: dict[str, Any]) -> str:
    """Format structured diagnostics for the LangChain tool response."""

    models = diagnostics.get("models", {})
    csv_files = diagnostics.get("csv_files", {})
    knowledge_base = diagnostics.get("knowledge_base", {})
    vector_store = diagnostics.get("vector_store", {})
    env = diagnostics.get("environment", {}).get("DASHSCOPE_API_KEY", {})
    notes = diagnostics.get("notes", [])

    return (
        "Agent自检结果如下：\n"
        f"- 总体状态：{diagnostics.get('overall_status', '未知')}\n"
        f"- 聊天模型：{models.get('chat_model', '未知')}\n"
        f"- Embedding模型：{models.get('embedding_model', '未知')}\n"
        "- 已注册工具列表：\n"
        + "\n".join(f"  - {name}" for name in diagnostics.get("tools", []))
        + "\n"
        "- 关键CSV文件：\n"
        + "\n".join(f"  - {path}：{'存在' if exists else '缺失'}" for path, exists in csv_files.items())
        + "\n"
        f"- 知识库目录：{knowledge_base.get('path', '未知')}（{'存在' if knowledge_base.get('exists') else '缺失'}）\n"
        f"- 向量库目录 rag/chroma_db：{'存在' if vector_store.get('exists') else '缺失'}\n"
        f"- DASHSCOPE_API_KEY：{'已配置' if env.get('exists') else '未配置'}\n"
        + "\n".join(f"说明：{note}" for note in notes)
    )
