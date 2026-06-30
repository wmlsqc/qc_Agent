"""Lightweight JSON memory for non-sensitive user preferences."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.csv_handler import find_first_csv_row
from utils.path_tool import get_abs_path


MEMORY_FILE = Path(get_abs_path("memory/user_memory.json"))
ALLOWED_FIELDS = {
    "user_id",
    "house_area_sqm",
    "family_size",
    "floor_type",
    "has_pet",
    "has_carpet",
    "common_faults",
    "cleaning_goal",
    "cleaning_preference",
    "preferred_cleaning_time",
    "frequent_cleaning_areas",
    "updated_at",
}
FAULT_KEYWORDS = ["漏扫", "不充电", "充不上电", "异响", "拖布不出水", "不出水", "无法回充", "找不到基站", "扫不干净"]


class LocalMemoryStore:
    """Read and write small user memory snapshots to a local JSON file."""

    def __init__(self, memory_file: str | Path = MEMORY_FILE):
        self.memory_file = Path(memory_file)

    def read_user_memory(self, user_id: str) -> dict[str, Any]:
        try:
            return dict(self._read_all().get(str(user_id), {}))
        except Exception:
            return {}

    def update_user_memory(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        try:
            clean_updates = self._sanitize_memory({"user_id": str(user_id), **updates})
            if not clean_updates:
                return self.read_user_memory(user_id)

            all_memory = self._read_all()
            current_memory = dict(all_memory.get(str(user_id), {}))
            merged_memory = self._merge_memory(current_memory, clean_updates)
            merged_memory["user_id"] = str(user_id)
            merged_memory["updated_at"] = datetime.now().isoformat(timespec="seconds")
            all_memory[str(user_id)] = merged_memory

            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            with self.memory_file.open("w", encoding="utf-8") as f:
                json.dump(all_memory, f, ensure_ascii=False, indent=2)
            return dict(merged_memory)
        except Exception:
            return self.read_user_memory(user_id)

    def _read_all(self) -> dict[str, dict[str, Any]]:
        if not self.memory_file.exists():
            return {}
        try:
            with self.memory_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _merge_memory(self, current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = self._sanitize_memory(current)
        for key, value in self._sanitize_memory(updates).items():
            if key == "common_faults":
                merged[key] = self._merge_list(merged.get(key, []), value)
            elif value not in [None, "", []]:
                merged[key] = value
        return self._sanitize_memory(merged)

    @staticmethod
    def _merge_list(old_items: Any, new_items: Any, limit: int = 8) -> list[str]:
        merged_items = []
        for item in list(old_items or []) + list(new_items or []):
            item_text = str(item).strip()
            if item_text and item_text not in merged_items:
                merged_items.append(item_text)
        return merged_items[-limit:]

    @staticmethod
    def _sanitize_memory(memory: dict[str, Any]) -> dict[str, Any]:
        clean_memory = {}
        for key, value in memory.items():
            if key not in ALLOWED_FIELDS or value in [None, "", []]:
                continue
            clean_memory[key] = value
        return clean_memory


def extract_memory_from_profile(user_id: str) -> dict[str, Any]:
    """Build non-sensitive memory from local mock user profile data."""

    try:
        profile = find_first_csv_row("data/external/users.csv", user_id=user_id)
        if not profile:
            return {}

        floor_type = profile.get("floor_type", "")
        has_pet = profile.get("has_pet", "")
        memory = {
            "user_id": user_id,
            "house_area_sqm": profile.get("area_sqm"),
            "family_size": profile.get("family_size"),
            "floor_type": floor_type,
            "has_pet": _is_yes(has_pet),
            "has_carpet": _has_carpet(floor_type),
        }

        cleaning_goal = profile.get("robot_usage_goal")
        preferred_time = profile.get("preferred_cleaning_time")
        if cleaning_goal:
            memory["cleaning_goal"] = cleaning_goal
        if preferred_time:
            memory["preferred_cleaning_time"] = preferred_time
        preference_parts = [part for part in [cleaning_goal, preferred_time] if part]
        if preference_parts:
            memory["cleaning_preference"] = "；".join(preference_parts)
        return memory
    except Exception:
        return {}


def extract_memory_from_message(message: str, user_id: str) -> dict[str, Any]:
    """Extract a small set of non-sensitive preferences from user text."""

    memory: dict[str, Any] = {"user_id": user_id}
    area_match = re.search(r"(\d{2,3})\s*(?:平|㎡|平方米)", message)
    if area_match:
        memory["house_area_sqm"] = area_match.group(1)

    if any(keyword in message for keyword in ["没有宠物", "无宠物", "不养宠物"]):
        memory["has_pet"] = False
    elif any(keyword in message for keyword in ["有宠物", "养猫", "养狗", "猫", "狗"]):
        memory["has_pet"] = True

    if any(keyword in message for keyword in ["没有地毯", "无地毯"]):
        memory["has_carpet"] = False
    elif "地毯" in message:
        memory["has_carpet"] = True

    faults = [keyword for keyword in FAULT_KEYWORDS if keyword in message]
    if faults:
        memory["common_faults"] = faults

    area_keywords = [
        "客厅",
        "卧室",
        "厨房",
        "阳台",
        "卫生间",
        "餐厅",
        "儿童房",
        "书房",
        "地毯",
        "猫砂盆",
        "狗窝",
        "沙发底部",
    ]
    frequent_areas = [keyword for keyword in area_keywords if keyword in message]
    if frequent_areas:
        memory["frequent_cleaning_areas"] = frequent_areas

    preference_terms = ["每天", "每周", "早上", "上午", "中午", "下午", "晚上", "夜间", "静音", "强力", "拖地", "扫拖", "预约"]
    if any(term in message for term in preference_terms):
        memory["cleaning_preference"] = _summarize_preference(message)

    return {key: value for key, value in memory.items() if value not in [None, "", []]}


def merge_memory_for_context(
    persisted_memory: dict[str, Any],
    session_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge persisted memory with Streamlit session memory taking priority."""

    merged = dict(persisted_memory or {})
    if session_memory:
        for key, value in session_memory.items():
            if key in ALLOWED_FIELDS and value not in [None, "", []]:
                merged[key] = value
    return LocalMemoryStore._sanitize_memory(merged)


def format_memory_context(memory: dict[str, Any]) -> str:
    if not memory:
        return "当前用户记忆：暂无可用记忆。"

    labels = {
        "user_id": "用户ID",
        "house_area_sqm": "房屋面积",
        "family_size": "家庭人数",
        "floor_type": "地面类型",
        "has_pet": "是否有宠物",
        "has_carpet": "是否有地毯",
        "common_faults": "常见故障",
        "cleaning_goal": "清扫目标",
        "cleaning_preference": "清扫偏好",
        "preferred_cleaning_time": "偏好清扫时间",
        "frequent_cleaning_areas": "常用清扫区域",
    }
    lines = ["当前用户记忆（仅供本轮个性化回答参考）："]
    for key in [
        "user_id",
        "house_area_sqm",
        "family_size",
        "floor_type",
        "has_pet",
        "has_carpet",
        "common_faults",
        "cleaning_goal",
        "cleaning_preference",
        "preferred_cleaning_time",
        "frequent_cleaning_areas",
    ]:
        if key not in memory:
            continue
        value = memory[key]
        if key == "house_area_sqm":
            value = f"{value}㎡"
        elif isinstance(value, bool):
            value = "是" if value else "否"
        elif isinstance(value, list):
            value = "、".join(str(item) for item in value)
        lines.append(f"- {labels[key]}：{value}")
    return "\n".join(lines)


def _summarize_preference(message: str) -> str:
    time_terms = [term for term in ["每天", "每周", "早上", "上午", "中午", "下午", "晚上", "夜间"] if term in message]
    mode_terms = [term for term in ["静音", "强力", "拖地", "扫拖", "预约"] if term in message]
    preference_parts = []
    if time_terms:
        preference_parts.append("时间偏好：" + "、".join(time_terms))
    if mode_terms:
        preference_parts.append("模式偏好：" + "、".join(mode_terms))
    return "；".join(preference_parts) or "日常清扫偏好"


def _is_yes(value: str) -> bool:
    normalized_value = str(value).strip().lower()
    return normalized_value in ["是", "yes", "true", "1"] or normalized_value.startswith("鏄")


def _has_carpet(value: str) -> bool:
    normalized_value = str(value)
    return "地毯" in normalized_value or "鍦版" in normalized_value
