import csv
import os
from typing import Any

from utils.logger_handler import logger
from utils.path_tool import get_abs_path


def read_csv_rows(csv_path: str, encoding: str = "utf-8") -> list[dict[str, str]]:
    """
    Read a CSV file and return rows as dictionaries.

    The path can be absolute or relative to the project root.
    """
    abs_path = csv_path if os.path.isabs(csv_path) else get_abs_path(csv_path)

    if not os.path.exists(abs_path):
        logger.warning(f"[read_csv_rows]CSV文件不存在: {abs_path}")
        return []

    with open(abs_path, "r", encoding=encoding, newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def filter_csv_rows(
    csv_path: str,
    *,
    encoding: str = "utf-8",
    **conditions: Any,
) -> list[dict[str, str]]:
    """
    Read a CSV file and return rows matching all non-empty conditions.
    """
    rows = read_csv_rows(csv_path, encoding=encoding)
    if not conditions:
        return rows

    result: list[dict[str, str]] = []
    for row in rows:
        matched = True
        for key, expected_value in conditions.items():
            if expected_value is None or expected_value == "":
                continue
            if row.get(key) != str(expected_value):
                matched = False
                break
        if matched:
            result.append(row)

    return result


def find_first_csv_row(
    csv_path: str,
    *,
    encoding: str = "utf-8",
    **conditions: Any,
) -> dict[str, str] | None:
    """
    Return the first CSV row matching all conditions, or None if not found.
    """
    rows = filter_csv_rows(csv_path, encoding=encoding, **conditions)
    return rows[0] if rows else None
