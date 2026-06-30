# 评估模块说明

`evaluations/` 目录提供轻量级回归检查，用于在开发后快速确认 Agent 的核心能力是否仍然稳定。

该评估不使用复杂的 LLM-as-judge，也不要求回答完全一致，而是直接调用工具或服务层，并检查输出中是否包含关键字段。

## 当前文件

- `test_cases.json`：测试用例和关键字段规则。
- `run_basic_checks.py`：基础检查脚本。
- `evaluation_report.md`：运行检查后生成的 Markdown 评估报告。

## 当前覆盖能力

- 开发调试：模型信息查询。
- 开发调试：Agent 自检。
- 设备状态查询。
- 耗材状态查询。
- 清扫历史查询。
- 故障诊断。
- 综合分析数据链。
- RAG 无资料兜底。

其中模型信息查询和 Agent 自检只作为开发者回归检查，不建议作为终端用户聊天能力展示。

## Docker 中运行

```powershell
docker compose exec -T agent-project python evaluations/run_basic_checks.py
```

默认报告输出到：

```text
evaluations/evaluation_report.md
```

也可以指定报告路径：

```powershell
docker compose exec -T agent-project python evaluations/run_basic_checks.py --report evaluations/evaluation_report.md
```

## 本地运行

```powershell
python evaluations/run_basic_checks.py
```

本地运行需要当前 Python 环境已安装 `requirements.txt` 中的依赖，并配置必要的环境变量。

## 报告内容

生成的 Markdown 报告包含：

- 测试时间
- 测试用例文件
- 测试用例数量
- 通过数量
- 失败数量
- 每个用例的检查结果
- 输出预览
- 风险提示

脚本会检查是否出现疑似密钥内容，例如 `sk-` 或 `DASHSCOPE_API_KEY=`，避免在报告中泄露 API Key。
