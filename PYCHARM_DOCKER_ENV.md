# PyCharm Docker 环境配置说明

当前项目推荐通过 Docker Compose 运行。为了避免 PyCharm 使用本地 Anaconda 环境时报出“不满足软件包要求”，可以把 PyCharm 的解释器配置为 Docker Compose 中的 Python 环境。

## 当前 Docker 环境

| 项目 | 值 |
| --- | --- |
| Compose 文件 | `D:\docker-projects\agent-project\docker-compose.yml` |
| Compose 服务 | `agent-project` |
| 容器 Python | `/usr/local/bin/python` |
| 容器端口 | `8501` |
| 宿主机端口 | `8502` |
| Web 地址 | `http://127.0.0.1:8502` |

## 在 PyCharm 中配置 Docker Compose 解释器

1. 用 PyCharm 打开 `D:\docker-projects\agent-project`。
2. 打开设置：`Ctrl + Alt + S`。
3. 进入 `Project: agent-project | Python Interpreter`。
4. 点击 `Add Interpreter`。
5. 选择 `On Docker Compose`。
6. `Server` 选择 Docker Desktop，或按默认配置新建 Docker Server。
7. `Configuration files` 选择：

   ```text
   D:\docker-projects\agent-project\docker-compose.yml
   ```

8. `Service` 选择：

   ```text
   agent-project
   ```

9. Python 解释器路径填写：

   ```text
   /usr/local/bin/python
   ```

10. 点击确认，等待 PyCharm 索引容器中的依赖。

配置完成后，PyCharm 应显示 Docker Compose 解释器，而不是本地 `D:\anaconda\python.exe`。

## 常用命令

启动项目：

```powershell
.\scripts\docker-up.ps1
```

查看日志：

```powershell
.\scripts\docker-logs.ps1
```

进入容器：

```powershell
.\scripts\docker-shell.ps1
```

## 验证 Docker 解释器

```powershell
docker compose ps
docker compose exec agent-project python --version
docker compose exec agent-project which python
```

如果 PyCharm 仍提示缺少依赖，通常说明当前项目解释器仍然指向本地 Python，而不是 Docker Compose 服务。
