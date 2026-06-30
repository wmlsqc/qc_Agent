"""Business data APIs backed by local CSV mock data."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from utils.csv_handler import find_first_csv_row, read_csv_rows


router = APIRouter(prefix="/users", tags=["business"])


def _to_int(value: str | None, default: int | None = None) -> int | None:
    try:
        return int(value or "")
    except (TypeError, ValueError):
        return default


def _to_bool(value: str | None) -> bool:
    return str(value or "").lower() == "true"


def _not_found(resource: str, user_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "success": False,
            "message": f"未查询到用户{user_id}的{resource}数据",
            "user_id": user_id,
        },
    )


@router.get("/{user_id}/profile")
def get_user_profile_api(user_id: str) -> dict[str, Any]:
    row = find_first_csv_row("data/external/users.csv", user_id=user_id)
    if not row:
        raise _not_found("用户画像", user_id)

    floor_type = row.get("floor_type", "")
    has_pet = row.get("has_pet", "")
    return {
        "success": True,
        "user_id": user_id,
        "data": {
            "name": row.get("name", ""),
            "city": row.get("city", ""),
            "home_type": row.get("home_type", ""),
            "area_sqm": _to_int(row.get("area_sqm")),
            "floor_type": floor_type,
            "has_pet": has_pet == "是" or has_pet.startswith("鏄"),
            "pet_type": row.get("pet_type", ""),
            "has_carpet": "地毯" in floor_type or "鍦版" in floor_type,
            "family_size": _to_int(row.get("family_size")),
            "robot_usage_goal": row.get("robot_usage_goal", ""),
            "preferred_cleaning_time": row.get("preferred_cleaning_time", ""),
        },
    }


@router.get("/{user_id}/robot-status")
def get_robot_status_api(user_id: str) -> dict[str, Any]:
    row = find_first_csv_row("data/external/devices.csv", user_id=user_id)
    if not row:
        raise _not_found("设备状态", user_id)

    return {
        "success": True,
        "user_id": user_id,
        "data": {
            "device_id": row.get("device_id", ""),
            "model": row.get("model", ""),
            "serial_no": row.get("serial_no", ""),
            "firmware_version": row.get("firmware_version", ""),
            "online_status": row.get("online_status", ""),
            "battery_percent": _to_int(row.get("battery_percent")),
            "current_mode": row.get("current_mode", ""),
            "dock_status": row.get("dock_status", ""),
            "last_cleaned_at": row.get("last_cleaned_at", ""),
            "last_error_code": row.get("last_error_code", ""),
            "last_error_message": row.get("last_error_message", ""),
            "map_version": row.get("map_version", ""),
            "water_tank_installed": _to_bool(row.get("water_tank_installed")),
        },
    }


@router.get("/{user_id}/consumables")
def get_consumables_api(user_id: str) -> dict[str, Any]:
    row = find_first_csv_row("data/external/consumables.csv", user_id=user_id)
    if not row:
        raise _not_found("耗材状态", user_id)

    consumables = {
        "main_brush_days_left": _to_int(row.get("main_brush_days_left")),
        "side_brush_days_left": _to_int(row.get("side_brush_days_left")),
        "filter_percent_left": _to_int(row.get("filter_percent_left")),
        "mop_pad_percent_left": _to_int(row.get("mop_pad_percent_left")),
        "dust_bag_percent_left": _to_int(row.get("dust_bag_percent_left")),
    }
    low_items = [
        key for key, value in consumables.items()
        if value is not None and 0 < value < 30
    ]

    return {
        "success": True,
        "user_id": user_id,
        "data": {
            "device_id": row.get("device_id", ""),
            "consumables": consumables,
            "low_items": low_items,
            "dust_bin_clean_frequency": row.get("dust_bin_clean_frequency", ""),
            "last_maintenance_at": row.get("last_maintenance_at", ""),
            "maintenance_advice": row.get("maintenance_advice", ""),
        },
    }


@router.get("/{user_id}/cleaning-history")
def get_cleaning_history_api(
    user_id: str,
    month: str | None = Query(default=None, description="可选月份，格式 YYYY-MM"),
) -> dict[str, Any]:
    rows = [
        row for row in read_csv_rows("data/external/cleaning_history.csv")
        if row.get("user_id") == user_id
    ]
    if month:
        rows = [row for row in rows if row.get("cleaning_date", "").startswith(month)]
    if not rows:
        raise _not_found("清扫历史", user_id)

    cleaning_count = len(rows)
    total_area = sum(_to_int(row.get("area_sqm"), 0) or 0 for row in rows)
    total_duration = sum(_to_int(row.get("duration_min"), 0) or 0 for row in rows)
    total_errors = sum(_to_int(row.get("error_count"), 0) or 0 for row in rows)
    average_duration = round(total_duration / cleaning_count, 1)
    average_coverage = round(
        sum(_to_int(row.get("coverage_percent"), 0) or 0 for row in rows) / cleaning_count,
        1,
    )
    missed_count = sum(
        1 for row in rows
        if row.get("missed_spots") and row.get("missed_spots") not in ["无", "none"]
    )
    mode_counts = Counter(row.get("mode", "unknown") for row in rows)
    common_mode = mode_counts.most_common(1)[0][0]

    records = sorted(
        rows,
        key=lambda row: f"{row.get('cleaning_date', '')} {row.get('start_time', '')}",
        reverse=True,
    )

    return {
        "success": True,
        "user_id": user_id,
        "data": {
            "month": month,
            "summary": {
                "cleaning_count": cleaning_count,
                "total_area_sqm": total_area,
                "average_duration_min": average_duration,
                "average_coverage_percent": average_coverage,
                "missed_count": missed_count,
                "error_count": total_errors,
                "common_mode": common_mode,
            },
            "records": records,
        },
    }
