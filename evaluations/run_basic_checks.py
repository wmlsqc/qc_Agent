"""Run lightweight regression checks for core Agent capabilities.

The checks call tools and services directly. They do not use LLM-as-judge and
do not require exact answer matching.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SECRET_PATTERNS = ["sk-", "DASHSCOPE_API_KEY="]
DEFAULT_CASES_PATH = PROJECT_ROOT / "evaluations" / "test_cases.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "evaluations" / "evaluation_report.md"


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("test_cases.json must contain a list")
    return data


def get_tool_registry() -> dict[str, Any]:
    from agent.tools import agent_tools

    return {
        "get_model_info": agent_tools.get_model_info,
        "get_agent_diagnostics": agent_tools.get_agent_diagnostics,
        "get_robot_status": agent_tools.get_robot_status,
        "get_consumable_status": agent_tools.get_consumable_status,
        "get_cleaning_history": agent_tools.get_cleaning_history,
        "get_user_profile": agent_tools.get_user_profile,
        "diagnose_fault": agent_tools.diagnose_fault,
    }


@contextmanager
def patched_rag_response(response: str | None):
    if response is None:
        yield
        return

    from agent.tools import agent_tools

    original_rag_summarize = agent_tools.rag.rag_summarize
    agent_tools.rag.rag_summarize = lambda query, with_sources=False: response
    try:
        yield
    finally:
        agent_tools.rag.rag_summarize = original_rag_summarize


def invoke_tool(tool: Any, args: dict[str, Any]) -> str:
    result = tool.invoke(args)
    return result if isinstance(result, str) else str(result)


def run_tool_case(case: dict[str, Any]) -> str:
    registry = get_tool_registry()
    tool_name = case["call"]
    if tool_name not in registry:
        raise KeyError(f"Unknown tool: {tool_name}")

    with patched_rag_response(case.get("mock_rag")):
        return invoke_tool(registry[tool_name], case.get("args", {}))


def run_composite_case(case: dict[str, Any]) -> str:
    registry = get_tool_registry()
    outputs = []
    for call_spec in case.get("calls", []):
        tool_name = call_spec["call"]
        if tool_name not in registry:
            raise KeyError(f"Unknown tool: {tool_name}")
        outputs.append(invoke_tool(registry[tool_name], call_spec.get("args", {})))
    return "\n".join(outputs)


def run_rag_case(case: dict[str, Any]) -> str:
    from rag.rag_service import RagSummarizeService

    return RagSummarizeService().rag_summarize(case["query"])


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    try:
        case_type = case["type"]
        if case_type == "tool":
            output = run_tool_case(case)
        elif case_type == "composite":
            output = run_composite_case(case)
        elif case_type == "rag":
            output = run_rag_case(case)
        else:
            raise ValueError(f"Unsupported case type: {case_type}")

        expected_keywords = case.get("expected_keywords", [])
        missing_keywords = [keyword for keyword in expected_keywords if keyword not in output]
        leaked_patterns = [pattern for pattern in SECRET_PATTERNS if pattern in output]
        passed = not missing_keywords and not leaked_patterns

        return {
            "id": case["id"],
            "name": case["name"],
            "passed": passed,
            "expected_keywords": expected_keywords,
            "missing_keywords": missing_keywords,
            "leaked_patterns": leaked_patterns,
            "output_preview": output[:300].replace("\n", "\\n"),
        }
    except Exception as exc:
        return {
            "id": case.get("id", "unknown"),
            "name": case.get("name", "unknown"),
            "passed": False,
            "error": str(exc),
            "expected_keywords": case.get("expected_keywords", []),
            "missing_keywords": case.get("expected_keywords", []),
            "leaked_patterns": [],
            "output_preview": "",
        }


def print_results(results: list[dict[str, Any]]) -> None:
    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    failed = total - passed

    print(f"Agent basic checks: {passed}/{total} passed, {failed} failed")
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {result['id']} - {result['name']}")
        if result.get("missing_keywords"):
            print(f"  missing_keywords: {', '.join(result['missing_keywords'])}")
        if result.get("leaked_patterns"):
            print("  leaked_patterns: detected forbidden secret-like content")
        if result.get("error"):
            print(f"  error: {result['error']}")
        if result.get("output_preview"):
            print(f"  preview: {result['output_preview']}")


def sanitize_report_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        text = text.replace(pattern, "[secret-like content removed]")
    return text.replace("|", "\\|")


def build_risk_notes(results: list[dict[str, Any]]) -> list[str]:
    notes = [
        "本评估为轻量关键字段检查，不等同于完整端到端业务验收。",
        "脚本直接调用工具或服务层，不使用复杂 LLM-as-judge，因此不会评判自然语言表达优劣。",
        "报告不会展示 API Key 内容；如果检测到密钥样式文本，仅记录为风险。",
    ]

    failed_results = [result for result in results if not result["passed"]]
    if failed_results:
        failed_ids = ", ".join(result["id"] for result in failed_results)
        notes.append(f"以下用例未通过，需要优先排查：{failed_ids}。")
    else:
        notes.append("本次基础检查全部通过，核心工具链当前状态稳定。")

    if any(result.get("leaked_patterns") for result in results):
        notes.append("检测到疑似敏感内容输出，请检查相关工具返回值和日志脱敏逻辑。")

    return notes


def write_markdown_report(
    results: list[dict[str, Any]], report_path: Path, cases_path: Path
) -> None:
    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    failed = total - passed
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# Agent 轻量评估报告",
        "",
        f"- 测试时间：{checked_at}",
        f"- 测试用例文件：`{cases_path}`",
        f"- 测试用例数量：{total}",
        f"- 通过数量：{passed}",
        f"- 失败数量：{failed}",
        "",
        "## 用例检查结果",
        "",
        "| 状态 | 用例 ID | 用例名称 | 缺失关键字段 | 风险 | 输出预览 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        missing = ", ".join(result.get("missing_keywords") or []) or "-"
        if result.get("leaked_patterns"):
            risk = "检测到疑似敏感内容"
        elif result.get("error"):
            risk = f"执行异常：{result['error']}"
        else:
            risk = "-"
        preview = result.get("output_preview") or "-"
        lines.append(
            "| {status} | `{case_id}` | {name} | {missing} | {risk} | {preview} |".format(
                status=status,
                case_id=sanitize_report_text(result["id"]),
                name=sanitize_report_text(result["name"]),
                missing=sanitize_report_text(missing),
                risk=sanitize_report_text(risk),
                preview=sanitize_report_text(preview),
            )
        )

    lines.extend(["", "## 风险提示", ""])
    lines.extend(f"- {sanitize_report_text(note)}" for note in build_risk_notes(results))
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight Agent checks.")
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES_PATH),
        help="Path to test_cases.json",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT_PATH),
        help="Path to write the Markdown evaluation report",
    )
    args = parser.parse_args()

    cases_path = Path(args.cases)
    report_path = Path(args.report)
    cases = load_cases(cases_path)
    results = [run_case(case) for case in cases]
    print_results(results)
    write_markdown_report(results, report_path, cases_path)
    print(f"Evaluation report written to: {report_path}")
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
