# API 模块说明

`api/` 目录提供当前项目的 FastAPI 服务入口，用于后续系统集成。它与 Streamlit Web 页面并存，不替换现有的聊天演示界面。

## 入口文件

- `api/main.py`：FastAPI 应用入口。
- `api/routes/business.py`：业务查询接口路由。

## 当前接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | API 健康检查 |
| GET | `/diagnostics` | 返回 Agent 诊断信息，复用 `services/diagnostics_service.py` |
| POST | `/chat` | 对话接口，复用 `services/chat_service.py` |
| GET | `/users/{user_id}/profile` | 查询用户画像 |
| GET | `/users/{user_id}/robot-status` | 查询用户绑定设备状态 |
| GET | `/users/{user_id}/consumables` | 查询用户耗材状态 |
| GET | `/users/{user_id}/cleaning-history` | 查询用户清扫历史，支持可选参数 `month` |

## 手动启动

在项目根目录运行：

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

启动后访问：

```text
http://127.0.0.1:8000/health
```

## Docker 内手动启动

```powershell
docker compose exec -T agent-project uvicorn api.main:app --host 0.0.0.0 --port 8000
```

当前 `docker-compose.yml` 默认只启动 Streamlit，并映射 `8502:8501`，没有发布 FastAPI 的 `8000` 端口。因此：

- 本机调试 FastAPI 时，推荐直接使用本地 `uvicorn` 启动。
- 容器内启动 FastAPI 主要用于容器内部调试。
- 如果后续要通过 Docker 对外提供 API，建议把 FastAPI 拆成独立 Compose service，并单独映射端口。

## 安全说明

`/diagnostics` 与 Agent 工具 `get_agent_diagnostics` 共用同一套诊断服务。接口返回结构化 JSON，只显示 `DASHSCOPE_API_KEY` 是否存在，不返回密钥内容。

示例请求中不要放真实 API Key。运行时密钥应保存在本地环境变量或 `.env` 文件中。

## PowerShell curl.exe 示例

以下示例默认 FastAPI 地址为：

```text
http://127.0.0.1:8000
```

健康检查：

```powershell
curl.exe http://127.0.0.1:8000/health
```

Agent 诊断：

```powershell
curl.exe http://127.0.0.1:8000/diagnostics
```

聊天接口：

```powershell
curl.exe -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"查询我的设备状态\",\"user_id\":\"1001\"}"
```

设备状态：

```powershell
curl.exe http://127.0.0.1:8000/users/1004/robot-status
```

耗材状态：

```powershell
curl.exe http://127.0.0.1:8000/users/1004/consumables
```

清扫历史：

```powershell
curl.exe "http://127.0.0.1:8000/users/1004/cleaning-history?month=2026-06"
```

## Invoke-RestMethod 示例

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Agent 诊断：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/diagnostics
```

聊天接口：

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"查询我的设备状态","user_id":"1001"}'
```

设备状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/users/1004/robot-status
```

耗材状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/users/1004/consumables
```

清扫历史：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/users/1004/cleaning-history?month=2026-06"
```
