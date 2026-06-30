# 服务层说明

`services/` 目录提供项目中相对稳定的应用服务入口。Streamlit、FastAPI 等上层入口应优先调用服务层，而不是直接拼装底层 Agent、RAG、记忆或规划模块。

## 当前文件

- `chat_service.py`：聊天服务入口，封装 ReactAgent 调用、用户 ID 识别、上下文构建、轻量记忆、轻量规划、寒暄兜底和异常友好提示。
- `diagnostics_service.py`：诊断服务，供 Agent 自检工具和 FastAPI `/diagnostics` 共用。

## ChatService 职责

`ChatService` 当前提供：

- `stream_chat()`：流式返回 Agent 回答，供 Streamlit 页面使用。
- `chat_once()`：一次性返回完整回答，供 FastAPI `/chat` 使用。
- `extract_user_id()`：从用户输入中识别用户 ID。
- `get_context_debug_summary()`：返回安全的上下文摘要。
- `reset_context_debug_summary()`：清空会话或切换用户后刷新上下文摘要。

聊天服务会处理：

- 普通寒暄，例如“你好”直接返回产品化欢迎语。
- 当前默认用户 ID。
- 最近会话历史裁剪。
- 轻量记忆上下文。
- 轻量规划上下文。
- DashScope 或模型连接异常时的友好提示。
- 移除面向用户回答中的参考来源信息。

## diagnostics_service 职责

诊断服务当前检查：

- 当前聊天模型名称。
- 当前 Embedding 模型名称。
- 已注册工具列表。
- 关键 CSV 文件是否存在。
- `rag/chroma_db` 是否存在。
- `.env` 是否配置 `DASHSCOPE_API_KEY`。

诊断结果内部使用结构化字典，工具层可以格式化成中文文本，API 层可以直接返回 JSON。诊断服务只显示 API Key 是否存在，不显示密钥内容。

## 设计边界

服务层不直接承担 UI 展示职责，也不保存真实业务数据。它主要用于统一 Streamlit、FastAPI 和后续扩展入口的调用方式，让二次开发时不必在多个入口里重复写 Agent 调用逻辑。
