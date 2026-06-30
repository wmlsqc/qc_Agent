"""Lightweight intent planner for the existing ReactAgent.

The planner only classifies the current user message and suggests a tool order.
It does not execute tools or replace the LangChain/LangGraph agent loop.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimplePlan:
    task_type: str
    tool_order: list[str]
    summary_focus: list[str]
    fallback: str


TASK_RULES: list[tuple[str, list[str], list[str], list[str]]] = [
    (
        "综合分析类",
        ["整体", "本月表现", "最近表现", "需要注意", "综合分析", "用得怎么样"],
        [
            "get_user_id",
            "get_user_profile",
            "get_robot_status",
            "get_consumable_status",
            "get_cleaning_history",
            "rag_summarize",
        ],
        ["设备状态", "耗材提醒", "清扫表现", "异常风险", "优化建议"],
    ),
    (
        "故障诊断类",
        ["漏扫", "不充电", "充不上电", "异响", "不出水", "无法回充", "找不到基站", "扫不干净"],
        ["get_user_id", "diagnose_fault", "rag_summarize"],
        ["可能原因", "排查步骤", "下一步建议"],
    ),
    (
        "设备状态类",
        ["设备状态", "电量", "在线", "离线", "当前模式", "基站", "最后清扫", "异常状态"],
        ["get_user_id", "get_robot_status"],
        ["设备型号", "在线状态", "电量", "当前模式", "异常提醒"],
    ),
    (
        "耗材类",
        ["耗材", "主刷", "边刷", "滤网", "拖布", "尘袋", "尘盒", "更换"],
        ["get_user_id", "get_consumable_status", "get_user_profile"],
        ["剩余寿命", "更换提醒", "保养建议"],
    ),
    (
        "清扫历史类",
        ["清扫记录", "清扫历史", "清扫效果", "最近使用", "覆盖率", "漏扫次数", "常用模式"],
        ["get_user_id", "get_cleaning_history", "get_user_profile"],
        ["清扫次数", "总面积", "平均时长", "异常次数", "使用建议"],
    ),
    (
        "知识问答类",
        ["怎么", "如何", "为什么", "保养", "维护", "适合", "区别", "建议"],
        ["rag_summarize"],
        ["专业知识", "适用条件", "操作建议"],
    ),
]

DEFAULT_PLAN = SimplePlan(
    task_type="知识问答类",
    tool_order=["rag_summarize"],
    summary_focus=["专业知识", "操作建议"],
    fallback="如果知识库没有有效资料，说明当前资料不足，并给出可确认的信息或建议用户补充细节。",
)


def build_simple_plan(message: str) -> SimplePlan:
    """Classify a message into a small set of supported task types."""

    normalized_message = message.lower()
    for task_type, keywords, tool_order, summary_focus in TASK_RULES:
        if any(keyword.lower() in normalized_message for keyword in keywords):
            return SimplePlan(
                task_type=task_type,
                tool_order=tool_order,
                summary_focus=summary_focus,
                fallback="如果某个工具调用失败或没有查到数据，不中断回答；基于已有信息总结，并明确说明缺失部分。",
            )
    return DEFAULT_PLAN


def build_planning_context(message: str) -> str:
    """Return a concise planning hint that can be prepended to the user turn."""

    plan = build_simple_plan(message)
    return (
        "轻量规划结果：\n"
        f"- 任务类型：{plan.task_type}\n"
        f"- 推荐工具顺序：{', '.join(plan.tool_order)}\n"
        f"- 总结重点：{', '.join(plan.summary_focus)}\n"
        f"- 兜底策略：{plan.fallback}"
    )
