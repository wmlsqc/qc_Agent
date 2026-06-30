# Docker 运行说明

本项目推荐使用 Docker Compose 运行 Streamlit Web 页面。依赖安装在镜像构建阶段完成，容器启动阶段只运行应用。

## 1. 配置环境变量

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 中填写真实的 DashScope API Key：

```env
DASHSCOPE_API_KEY=your-dashscope-api-key
```

注意：`.env` 只保存在本机，不要提交到 GitHub。

## 2. 构建镜像

首次运行或依赖变化后执行：

```powershell
docker compose up -d --build --remove-orphans
```

日常启动如果没有改动依赖，可以执行：

```powershell
docker compose up -d
```

## 3. 访问 Web 页面

当前 `docker-compose.yml` 映射端口为：

```text
8502:8501
```

浏览器访问：

```text
http://127.0.0.1:8502
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8502/_stcore/health
```

正常返回：

```text
ok
```

## 4. 初始化或重建向量库

如果需要重新构建 RAG 向量库，可以执行：

```powershell
docker compose exec -T agent-project python rag/vector_store.py
```

该步骤会调用 Embedding 模型，需要 `.env` 中配置有效的 `DASHSCOPE_API_KEY`。

## 5. 常用命令

查看容器：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f agent-project
```

进入容器：

```powershell
docker compose exec agent-project sh
```

停止服务：

```powershell
docker compose down
```

## 6. 不应上传的 Docker 运行产物

以下内容不应上传到 GitHub：

- `.env`
- Docker 镜像和容器本身
- `logs/`
- `rag/chroma_db/`
- `memory/user_memory.json`
- `__pycache__/`

GitHub 只需要保存 `Dockerfile`、`docker-compose.yml`、`.dockerignore`、`.env.example` 和相关脚本。
