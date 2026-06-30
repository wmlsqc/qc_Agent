# 智扫通机器人智能客服 Agent

这是一个面向扫地机器人和扫拖一体机器人场景的智能客服 Agent 项目。项目以 Streamlit 作为 Web 演示入口，以 ReactAgent 作为核心智能体，结合本地 CSV 业务数据、RAG 知识库、轻量上下文、轻量记忆、工具调用日志、FastAPI 扩展接口和基础评估脚本，支持设备状态查询、耗材寿命查询、清扫历史分析、故障诊断和使用报告生成。

当前项目定位为教学、演示和二次开发原型。业务数据仍是本地模拟数据，不是真实线上接口。

## 技术栈

| 类型 | 技术 |
| --- | --- |
| Web 页面 | Streamlit |
| Agent | LangChain / LangGraph 风格 ReactAgent |
| 聊天模型 | DashScope 通义千问 `qwen3-max` |
| Embedding | DashScope `text-embedding-v4` |
| 向量库 | ChromaDB |
| 知识库 | TXT / PDF + RAG |
| 业务数据 | 本地 CSV |
| 轻量记忆 | 本地 JSON |
| API 扩展 | FastAPI |
| 容器化 | Docker Compose |

## 项目结构

```text
agent-project/
├── app.py                         # Streamlit Web 入口
├── agent/
│   ├── react_agent.py             # ReactAgent 创建与工具注册
│   └── tools/
│       ├── agent_tools.py         # Agent 工具函数
│       └── middleware.py          # 工具调用日志、中间件
├── api/
│   ├── main.py                    # FastAPI 入口
│   └── routes/business.py         # 业务查询接口
├── config/                        # YAML 配置
├── context/context_builder.py     # 轻量上下文构建
├── data/
│   ├── external/                  # 本地模拟业务数据
│   └── *.txt / *.pdf              # RAG 知识库资料
├── docs/                          # 汇报文档
├── evaluations/                   # 轻量评估用例和报告
├── memory/local_memory.py         # 本地 JSON 记忆
├── model/factory.py               # 模型工厂
├── planning/simple_planner.py     # 轻量任务规划
├── prompts/                       # Agent / RAG / 报告提示词
├── rag/                           # RAG 检索与向量库构建
├── scripts/                       # Docker 和回归检查脚本
├── services/                      # ChatService、诊断服务
├── utils/                         # 配置、CSV、文件、日志工具
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 核心能力

### 1. 工具调用

Agent 可以根据用户问题选择工具，并把工具结果整理为自然语言回答。主要工具包括：

| 工具 | 作用 |
| --- | --- |
| `rag_summarize` | 从扫地机器人知识库检索并总结答案 |
| `get_user_id` | 获取当前默认用户 ID |
| `get_user_profile` | 查询用户画像和家庭场景 |
| `get_robot_status` | 查询扫地机器人设备状态 |
| `get_consumable_status` | 查询主刷、边刷、滤网、拖布、集尘袋等耗材寿命 |
| `get_cleaning_history` | 查询清扫历史并汇总使用表现 |
| `diagnose_fault` | 结合知识库、设备状态和清扫历史进行故障诊断 |
| `fetch_external_data` | 查询原有月度报告数据 |
| `fill_context_for_report` | 触发使用报告生成流程 |
| `get_weather` | 模拟天气查询 |
| `get_user_location` | 模拟用户城市 |
| `get_current_month` | 模拟当前月份 |

开发调试类工具包括 `get_model_info` 和 `get_agent_diagnostics`。它们用于本地检查、评估脚本和 FastAPI `/diagnostics`，不建议作为面向真实用户的产品聊天能力展示。

### 2. RAG 知识库问答

RAG 模块位于 `rag/`：

- `rag/vector_store.py`：读取知识库文件，切分文本，写入 ChromaDB。
- `rag/rag_service.py`：检索、相关性过滤、来源去重和回答生成。

知识库资料位于 `data/`，包括故障排除、维护保养、选购指南和常见问答。当前 RAG 在资料不足时会返回明确兜底提示，避免编造知识库中没有的结论。

### 3. 本地模拟业务数据

业务数据位于 `data/external/`：

| 文件 | 当前行数 | 用途 |
| --- | ---: | --- |
| `users.csv` | 10 | 用户画像、房屋面积、宠物、地毯、清扫偏好 |
| `devices.csv` | 10 | 设备型号、在线状态、电量、模式、异常状态 |
| `consumables.csv` | 10 | 主刷、边刷、滤网、拖布、集尘袋等耗材寿命 |
| `cleaning_history.csv` | 13 | 清扫次数、面积、时长、覆盖率、异常和漏扫记录 |
| `records.csv` | 120 | 原有月度报告生成数据 |

CSV 统一由 `utils/csv_handler.py` 读取，使用 UTF-8 编码。

### 4. 用户 ID 与会话上下文

项目支持从用户输入中识别用户 ID，例如：

```text
我是用户1001
查询用户1004的设备状态
user_id: 1002
```

如果用户没有指定 ID，则使用 Streamlit 侧边栏当前选择的用户 ID。每个用户 ID 在当前 Streamlit 会话中拥有独立聊天历史；切换用户后，页面展示该用户自己的会话记录。

上下文构建逻辑位于 `context/context_builder.py`，默认只保留最近约 5 轮对话，避免把无限历史传给模型。

### 5. 轻量记忆

记忆模块位于 `memory/local_memory.py`，运行时文件为：

```text
memory/user_memory.json
```

记忆只保存非敏感业务信息，例如用户 ID、房屋面积、是否有宠物、是否有地毯、常见故障、清扫偏好等。不会保存 API Key、密码、账号凭据、电话、地址或完整原始聊天隐私内容。

### 6. 轻量规划

`planning/simple_planner.py` 会根据用户问题识别任务类型，并提示 Agent 优先选择合适工具。当前覆盖：

- 设备状态类
- 耗材类
- 清扫历史类
- 故障诊断类
- 综合分析类
- 知识问答类

该规划模块是轻量辅助，不是复杂多智能体系统。

### 7. 故障诊断

`diagnose_fault(issue, user_id="")` 支持对漏扫、不充电、异响、拖布不出水、无法回充等问题做初步诊断。回答结构包含：

- 可能原因
- 排查步骤
- 风险等级
- 是否建议售后
- 下一步建议

如果传入用户 ID，诊断会尝试结合该用户设备状态和清扫历史。

### 8. FastAPI 扩展

FastAPI 与 Streamlit 并存，不替代 Web 页面。入口为 `api/main.py`。

当前接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | API 健康检查 |
| GET | `/diagnostics` | 返回 Agent 诊断信息，JSON 格式 |
| POST | `/chat` | 调用 ChatService 进行对话 |
| GET | `/users/{user_id}/profile` | 查询用户画像 |
| GET | `/users/{user_id}/robot-status` | 查询设备状态 |
| GET | `/users/{user_id}/consumables` | 查询耗材状态 |
| GET | `/users/{user_id}/cleaning-history` | 查询清扫历史，支持 `month` 参数 |

Docker Compose 默认只启动 Streamlit。如果要单独启动 FastAPI，可在本机运行：

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

然后访问：

```text
http://127.0.0.1:8000/health
```

更多 API 示例见 `api/README.md`。

## Docker Compose 运行

当前 Compose 配置：

| 项目 | 值 |
| --- | --- |
| 服务名 | `agent-project` |
| 容器名 | `agent-project` |
| 镜像名 | `agent-project:local` |
| 容器端口 | `8501` |
| 宿主机端口 | `8502` |
| Web 地址 | `http://127.0.0.1:8502` |

依赖安装在 Dockerfile 构建阶段完成。Compose 启动阶段只负责启动 Streamlit，因此日常 `docker compose up -d` 不会重复执行 `pip install -r requirements.txt`。

启动：

```powershell
cd D:\docker-projects\agent-project
docker compose up -d
```

重新构建并清理旧容器：

```powershell
docker compose up -d --build --remove-orphans
```

当 `requirements.txt`、`Dockerfile` 或基础镜像发生变化时，需要使用上面的 `--build` 命令重新构建镜像。

查看容器：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f agent-project
```

停止：

```powershell
docker compose down
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8502/_stcore/health
```

正常返回：

```text
ok
```

## 本地 Python 运行

安装依赖：

```powershell
pip install -r requirements.txt
```

配置环境变量：

```powershell
$env:DASHSCOPE_API_KEY="your-api-key-here"
```

启动 Streamlit：

```powershell
streamlit run app.py
```

默认访问：

```text
http://localhost:8501
```

## 初始化或重建向量库

首次使用 RAG 前，需要将 `data/` 下的 TXT/PDF 知识文件写入 ChromaDB：

```powershell
python rag/vector_store.py
```

Docker 内执行：

```powershell
docker compose exec -T agent-project python rag/vector_store.py
```

向量库目录：

```text
rag/chroma_db
```

## 基础验证

推荐每次改动后运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_project_checks.ps1
```

该脚本会检查：

- Python 关键模块编译
- Agent 自检
- CSV 文件读取
- RAG 无资料兜底
- Streamlit health
- evaluations 基础用例

通过时通常会看到类似输出：

```text
Project regression checks passed.
Agent basic checks: 8/8 passed, 0 failed
```

## 可以演示的问题

推荐演示扫地机器人业务问题：

```text
你好
查询我的扫地机器人设备状态
查询用户1004的设备状态
我的滤网和主刷还要不要换？
查询我最近的清扫记录
帮我整体分析一下本月表现
我的扫地机器人无法回充，请帮我诊断
生成我的扫地机器人使用报告
扫地机器人在潮湿天气下如何保养？
小户型适合哪些扫地机器人？
```

不建议作为产品演示的问题：

```text
你的底层调用的是什么模型？
系统状态怎么样？
项目是否正常？
有哪些工具？
```

这类问题属于开发者调试或项目验收范围，不适合作为真实客服产品能力暴露给终端用户。项目中已将这类能力尽量限制在调试入口和 API 诊断接口中。

## 环境变量与安全

项目需要配置：

```env
DASHSCOPE_API_KEY=your-api-key-here
```

注意：

- 不要提交 `.env`。
- 不要在 README、日志或前端页面展示真实 API Key。
- 诊断接口只显示 API Key 是否存在，不显示密钥内容。
- `memory/user_memory.json` 属于运行时文件，不应提交。

## 进一步改进建议

1. 固定依赖版本，减少重新构建时因第三方库升级带来的不确定性；可以逐步引入 `requirements.lock` 或类似锁定文件。
2. 将 Streamlit 和 FastAPI 拆成两个 Docker Compose service，让 Web 演示入口和系统集成接口可以独立启动、独立扩展。
3. 将本地 CSV 模拟数据替换为真实业务接口，例如设备平台、用户系统、耗材库存系统和售后工单系统。
4. 将本地 JSON 轻量记忆升级为更适合多人并发的存储方式，并增加记忆过期、用户授权和敏感信息过滤规则。
5. 优化 RAG 检索质量，引入重排序、知识标签、故障类型分类和更严格的无资料兜底策略。
6. 扩展评估体系，从关键字段检查升级为更完整的业务用例、工具调用断言、回答质量评分和回归报告。
7. 明确区分真实工具和演示工具，逐步替换 `get_weather`、`get_user_location`、`get_current_month` 等模拟能力。
8. 按运行模式区分“用户工具”和“开发工具”，避免模型信息、自检工具等调试能力在产品聊天入口中被误触发。
9. 如果 FastAPI 对外开放，需要增加鉴权、限流、参数校验、日志脱敏和访问审计。
