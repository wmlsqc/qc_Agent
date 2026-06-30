import random
from utils.config_handler import agent_conf, chroma_conf, rag_conf
from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
from services.diagnostics_service import build_agent_diagnostics, format_agent_diagnostics
from utils.csv_handler import find_first_csv_row, read_csv_rows
from utils.path_tool import get_abs_path
from utils.logger_handler import logger

rag = RagSummarizeService()
user_ids = ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1009", "1010",]
month_arr = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
             "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", ]
external_data = {}
current_user_id = user_ids[0]

REGISTERED_TOOL_DESCRIPTIONS = [
    "rag_summarize: 扫地/扫拖机器人知识库检索",
    "get_weather: 城市天气与环境信息查询",
    "get_user_location: 获取用户所在城市",
    "get_user_id: 获取当前用户ID",
    "get_current_month: 获取当前月份",
    "fetch_external_data: 查询用户月度使用记录",
    "fill_context_for_report: 触发报告生成上下文",
    "get_model_info: 查询当前智能体模型和配置",
    "get_agent_diagnostics: 检查Agent、模型、工具、数据文件和向量库状态",
    "get_user_profile: 查询用户家庭场景、宠物、地面和清扫偏好",
    "get_robot_status: 查询用户绑定扫地机器人设备状态",
    "get_consumable_status: 查询主刷、边刷、滤网、拖布、集尘袋等耗材状态",
    "get_cleaning_history: 查询用户清扫历史和清扫效果汇总",
    "diagnose_fault: 针对漏扫、不充电、异响、拖布不出水、无法回充等问题进行初步诊断",
]


def set_current_user_id(user_id: str | None) -> str:
    """Set the current session user id used by get_user_id."""

    global current_user_id
    if user_id:
        current_user_id = str(user_id)
    return current_user_id


def _safe_int(value: str | None, default: int | None = None) -> int | None:
    try:
        return int(value or "")
    except (TypeError, ValueError):
        return default


def _format_key_values(data: dict[str, object]) -> str:
    return "\n".join(f"- {key}：{value}" for key, value in data.items())


def _format_bullets(items: list[str]) -> str:
    if not items:
        return "- 暂无"
    return "\n".join(f"- {item}" for item in items)


def _format_numbered_steps(items: list[str]) -> str:
    if not items:
        return "1. 暂无"
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _remove_reference_sources(text: str) -> str:
    """Remove source citation blocks from text shown to end users."""

    if not text:
        return ""
    markers = ["参考来源：", "参考来源:", "来源：", "来源:"]
    cleaned_text = text
    for marker in markers:
        if marker in cleaned_text:
            cleaned_text = cleaned_text.split(marker, 1)[0]
    return cleaned_text.strip()


@tool(description='从向量存储中检索参考资料')
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)

@tool(description="获取当前智能体的模型配置、知识库配置和主要工具能力")
def get_model_info() -> str:
    knowledge_path = get_abs_path(chroma_conf["data_path"])
    vector_path = get_abs_path(chroma_conf["persist_directory"])

    return (
        "当前智能体配置信息如下：\n"
        f"- 聊天模型：{rag_conf['chat_model_name']}\n"
        f"- Embedding模型：{rag_conf['embedding_model_name']}\n"
        f"- 向量数据库：ChromaDB，集合名 {chroma_conf['collection_name']}\n"
        f"- 知识库目录：{knowledge_path}\n"
        f"- 向量库目录：{vector_path}\n"
        f"- 检索返回数量：top {chroma_conf['k']}\n"
        "- 主要工具能力：\n"
        + "\n".join(f"  - {name}" for name in REGISTERED_TOOL_DESCRIPTIONS)
    )


@tool(description="检查当前Agent、模型、工具、CSV数据文件、向量库和环境变量是否可用")
def get_agent_diagnostics() -> str:
    diagnostics = build_agent_diagnostics(REGISTERED_TOOL_DESCRIPTIONS)
    return format_agent_diagnostics(diagnostics)


@tool(description="根据用户ID查询用户家庭场景、地面、宠物和清扫偏好画像")
def get_user_profile(user_id: str) -> str:
    try:
        profile = find_first_csv_row("data/external/users.csv", user_id=user_id)
        if not profile:
            logger.warning(f"[get_user_profile]未查询到用户{user_id}画像")
            return f"未查询到用户ID为{user_id}的用户画像，请确认用户ID是否正确。"

        floor_type = profile.get("floor_type", "未知")
        has_pet = profile.get("has_pet", "未知")
        pet_type = profile.get("pet_type") or "无"
        carpet_status = "有地毯或地毯场景" if "地毯" in floor_type else "未记录明显地毯场景"
        pet_status = f"有宠物，类型：{pet_type}" if has_pet == "是" else "无宠物"

        profile_data = {
            "用户ID": profile.get("user_id", user_id),
            "姓名": profile.get("name", "未知"),
            "城市": profile.get("city", "未知"),
            "住宅类型": profile.get("home_type", "未知"),
            "房屋面积": f"{profile.get('area_sqm', '未知')}㎡",
            "房间数量": profile.get("room_count") or profile.get("rooms") or "未配置",
            "地面材质": floor_type,
            "地毯情况": carpet_status,
            "宠物情况": pet_status,
            "家庭人数": profile.get("family_size", "未知"),
            "清扫目标": profile.get("robot_usage_goal", "未知"),
            "偏好清扫时间": profile.get("preferred_cleaning_time", "未知"),
        }

        personalized_tips = []
        if has_pet == "是":
            personalized_tips.append("家庭有宠物，建议重点关注主刷缠绕、滤网清洁和毛发聚集区域。")
        if "地毯" in floor_type:
            personalized_tips.append("存在地毯场景，建议开启地毯增压并关注地毯边缘漏扫。")
        if profile.get("area_sqm") and (_safe_int(profile.get("area_sqm"), 0) or 0) >= 100:
            personalized_tips.append("房屋面积较大，建议分区清扫并关注续航和回充完成率。")
        if not personalized_tips:
            personalized_tips.append("当前家庭场景较常规，可按日常灰尘清理和定期保养策略使用。")

        structured_result = {
            "user_id": user_id,
            "profile": profile_data,
            "personalized_tips": personalized_tips,
        }

        return (
            f"用户{structured_result['user_id']}的用户画像如下：\n"
            f"{_format_key_values(structured_result['profile'])}\n"
            "个性化参考：\n"
            f"{_format_bullets(structured_result['personalized_tips'])}"
        )
    except Exception as e:
        logger.exception(f"[get_user_profile]查询用户{user_id}画像失败: {str(e)}")
        return f"查询用户{user_id}画像时出现异常，请稍后重试或检查本地用户画像数据文件。"


@tool(description="根据用户ID查询用户绑定的扫地机器人设备状态")
def get_robot_status(user_id: str) -> str:
    try:
        device = find_first_csv_row("data/external/devices.csv", user_id=user_id)
        if not device:
            logger.warning(f"[get_robot_status]未查询到用户{user_id}绑定的设备")
            return f"未查询到用户ID为{user_id}的绑定设备信息，请确认用户ID是否正确。"

        online_status_map = {
            "online": "在线",
            "offline": "离线",
        }
        mode_map = {
            "auto": "自动清扫",
            "mop": "拖地模式",
            "carpet_boost": "地毯增压",
            "quiet": "安静模式",
            "zone": "分区清扫",
            "edge": "沿边清扫",
            "max": "强力清扫",
        }
        dock_status_map = {
            "docked": "已在基站",
            "cleaning": "正在清扫",
            "undocked": "未在基站",
            "returning": "正在回充",
        }

        battery_percent = _safe_int(device.get("battery_percent"))
        error_code = device.get("last_error_code") or "无"
        error_message = device.get("last_error_message") or "当前未记录异常"
        status_data = {
            "设备ID": device.get("device_id", "未知"),
            "设备型号": device.get("model", "未知"),
            "序列号": device.get("serial_no", "未知"),
            "固件版本": device.get("firmware_version", "未知"),
            "在线状态": online_status_map.get(device.get("online_status", ""), device.get("online_status", "未知")),
            "电量": f"{battery_percent}%" if battery_percent is not None else "未知",
            "当前模式": mode_map.get(device.get("current_mode", ""), device.get("current_mode", "未知")),
            "基站状态": dock_status_map.get(device.get("dock_status", ""), device.get("dock_status", "未知")),
            "最后清扫时间": device.get("last_cleaned_at", "未知"),
            "异常状态": f"{error_code}，{error_message}",
            "地图版本": device.get("map_version", "未知"),
            "水箱状态": "已安装" if device.get("water_tank_installed") == "true" else "未安装",
        }

        reminders = []
        if device.get("online_status") == "offline":
            reminders.append("设备当前离线，建议先确认网络、电源和基站连接。")
        if battery_percent is not None and battery_percent < 20:
            reminders.append("设备电量偏低，建议优先回充后再执行清扫任务。")
        if error_code != "无":
            reminders.append(f"设备存在异常记录：{error_code}，{error_message}。")
        if not reminders:
            reminders.append("设备状态整体正常。")

        structured_result = {
            "user_id": user_id,
            "status": status_data,
            "reminders": reminders,
        }

        return (
            f"用户{structured_result['user_id']}绑定设备状态如下：\n"
            f"{_format_key_values(structured_result['status'])}\n"
            "状态提醒：\n"
            f"{_format_bullets(structured_result['reminders'])}"
        )
    except Exception as e:
        logger.exception(f"[get_robot_status]查询用户{user_id}设备状态失败: {str(e)}")
        return f"查询用户{user_id}设备状态时出现异常，请稍后重试或检查本地设备数据文件。"

@tool(description="根据用户ID查询扫地机器人的耗材寿命和保养建议")
def get_consumable_status(user_id: str) -> str:
    try:
        consumable = find_first_csv_row("data/external/consumables.csv", user_id=user_id)
        if not consumable:
            logger.warning(f"[get_consumable_status]未查询到用户{user_id}的耗材状态")
            return f"未查询到用户ID为{user_id}的耗材状态，请确认用户ID是否正确。"

        def build_item(label: str, field: str, unit: str) -> dict[str, object]:
            value = _safe_int(consumable.get(field))
            if value is None:
                return {
                    "name": label,
                    "remaining": "未知",
                    "status": "未知",
                    "recommend_replace": False,
                    "message": f"{label}寿命未知",
                }
            if value <= 0:
                return {
                    "name": label,
                    "remaining": "不适用或未配置",
                    "status": "未配置",
                    "recommend_replace": False,
                    "message": f"{label}不适用或未配置",
                }
            if value < 30:
                return {
                    "name": label,
                    "remaining": f"{value}{unit}",
                    "status": "偏低",
                    "recommend_replace": True,
                    "message": f"{label}剩余{value}{unit}，建议尽快更换或清洁",
                }
            return {
                "name": label,
                "remaining": f"{value}{unit}",
                "status": "正常",
                "recommend_replace": False,
                "message": f"{label}剩余{value}{unit}，状态正常",
            }

        items = [
            build_item("主刷", "main_brush_days_left", "天"),
            build_item("边刷", "side_brush_days_left", "天"),
            build_item("滤网", "filter_percent_left", "%"),
            build_item("拖布", "mop_pad_percent_left", "%"),
            build_item("集尘袋", "dust_bag_percent_left", "%"),
        ]
        warnings = [str(item["message"]) for item in items if item["recommend_replace"]]
        summary = {
            "设备ID": consumable.get("device_id", "未知"),
            "尘盒清理频率": consumable.get("dust_bin_clean_frequency", "未知"),
            "上次保养时间": consumable.get("last_maintenance_at", "未知"),
            "更换提醒": "需要重点关注：" + "；".join(warnings) if warnings else "暂无低寿命耗材提醒",
            "保养建议": consumable.get("maintenance_advice", "暂无"),
        }
        item_lines = [
            f"- {item['name']}：{item['remaining']}，状态：{item['status']}"
            for item in items
        ]
        structured_result = {
            "user_id": user_id,
            "items": items,
            "summary": summary,
            "warnings": warnings,
        }

        return (
            f"用户{structured_result['user_id']}的耗材状态如下：\n"
            + "\n".join(item_lines)
            + "\n"
            f"{_format_key_values(structured_result['summary'])}"
        )
    except Exception as e:
        logger.exception(f"[get_consumable_status]查询用户{user_id}耗材状态失败: {str(e)}")
        return f"查询用户{user_id}耗材状态时出现异常，请稍后重试或检查本地耗材数据文件。"

@tool(description="根据用户ID和可选月份查询清扫历史汇总")
def get_cleaning_history(user_id: str, month: str = "") -> str:
    try:
        rows = [
            row for row in read_csv_rows("data/external/cleaning_history.csv")
            if row.get("user_id") == user_id
        ]
        if month:
            rows = [row for row in rows if row.get("cleaning_date", "").startswith(month)]

        if not rows:
            month_text = f"{month}月份" if month else "最近"
            logger.warning(f"[get_cleaning_history]未查询到用户{user_id}的{month_text}清扫记录")
            return f"未查询到用户ID为{user_id}的{month_text}清扫记录，请确认用户ID或月份是否正确。"

        mode_map = {
            "auto": "自动清扫",
            "mop": "拖地模式",
            "carpet_boost": "地毯增压",
            "quiet": "安静模式",
            "zone": "分区清扫",
            "edge": "沿边清扫",
            "max": "强力清扫",
        }

        cleaning_count = len(rows)
        total_area = sum(_safe_int(row.get("area_sqm"), 0) or 0 for row in rows)
        total_duration = sum(_safe_int(row.get("duration_min"), 0) or 0 for row in rows)
        avg_duration = round(total_duration / cleaning_count, 1)
        avg_coverage = round(
            sum(_safe_int(row.get("coverage_percent"), 0) or 0 for row in rows) / cleaning_count,
            1,
        )
        missed_count = sum(
            1 for row in rows
            if row.get("missed_spots") and row.get("missed_spots") not in ["无", "none"]
        )
        error_count = sum(_safe_int(row.get("error_count"), 0) or 0 for row in rows)

        mode_counter: dict[str, int] = {}
        for row in rows:
            mode = row.get("mode", "unknown")
            mode_counter[mode] = mode_counter.get(mode, 0) + 1
        common_mode = max(mode_counter, key=mode_counter.get)
        common_mode_text = mode_map.get(common_mode, common_mode)

        sorted_rows = sorted(
            rows,
            key=lambda row: f"{row.get('cleaning_date', '')} {row.get('start_time', '')}",
            reverse=True,
        )
        recent_records = []
        for row in sorted_rows[:3]:
            mode_text = mode_map.get(row.get("mode", ""), row.get("mode", "未知"))
            recent_records.append({
                "date": row.get("cleaning_date", "未知日期"),
                "start_time": row.get("start_time", ""),
                "mode": mode_text,
                "area_sqm": row.get("area_sqm", "未知"),
                "coverage_percent": row.get("coverage_percent", "未知"),
                "summary": row.get("summary", "无"),
            })

        suggestions = []
        if missed_count > 0:
            suggestions.append("存在漏扫记录，建议清扫前整理地面线缆、玩具和椅脚区域。")
        if error_count > 0:
            suggestions.append("存在异常次数，建议结合设备状态或故障码进一步排查。")
        if avg_coverage < 85:
            suggestions.append("平均覆盖率偏低，建议检查地图、禁区设置和基站摆放位置。")
        if not suggestions:
            suggestions.append("整体清扫表现稳定，可继续保持当前清扫计划。")

        month_text = f"{month}月份" if month else "最近"
        summary_data = {
            "清扫次数": f"{cleaning_count}次",
            "总清扫面积": f"{total_area}㎡",
            "平均清扫时长": f"{avg_duration}分钟",
            "平均覆盖率": f"{avg_coverage}%",
            "漏扫记录数": f"{missed_count}次",
            "异常次数": f"{error_count}次",
            "常用模式": common_mode_text,
        }
        record_lines = [
            f"- {record['date']} {record['start_time']}，{record['mode']}，"
            f"面积{record['area_sqm']}㎡，覆盖率{record['coverage_percent']}%，"
            f"摘要：{record['summary']}"
            for record in recent_records
        ]
        structured_result = {
            "user_id": user_id,
            "period": month_text,
            "summary": summary_data,
            "recent_records": recent_records,
            "suggestions": suggestions,
        }

        return (
            f"用户{structured_result['user_id']}的{structured_result['period']}清扫历史汇总如下：\n"
            f"{_format_key_values(structured_result['summary'])}\n"
            "最近记录：\n"
            + "\n".join(record_lines)
            + "\n"
            "使用建议：\n"
            f"{_format_bullets(structured_result['suggestions'])}"
        )
    except Exception as e:
        logger.exception(f"[get_cleaning_history]查询用户{user_id}清扫历史失败: {str(e)}")
        return f"查询用户{user_id}清扫历史时出现异常，请稍后重试或检查本地清扫历史数据文件。"

@tool(description="根据故障描述和可选用户ID进行扫地机器人初步故障诊断")
def diagnose_fault(issue: str, user_id: str = "") -> str:
    try:
        issue_text = issue.strip()
        if not issue_text:
            return "请提供具体故障现象，例如漏扫、不充电、异响、拖布不出水或无法回充。"

        fault_rules = [
            {
                "keywords": ["漏扫", "扫不干净", "覆盖率低", "没扫到", "遗漏"],
                "name": "漏扫或覆盖不完整",
                "risk_level": "中",
                "causes": [
                    "地图未更新或房间分区存在偏差",
                    "地面有线缆、玩具、椅脚等障碍物影响路径规划",
                    "传感器、边刷或主刷有灰尘和毛发堆积",
                    "低矮家具、门槛或地毯边缘导致机器人无法进入",
                ],
                "steps": [
                    "先整理地面障碍物，特别是线缆、玩具、椅脚和地毯边缘",
                    "清洁前视、沿墙和悬崖传感器，并检查边刷、主刷是否缠绕",
                    "在 App 中更新或重建地图，确认禁区、虚拟墙和房间分区设置",
                    "对经常漏扫的位置设置定点清扫或分区清扫，再观察覆盖率变化",
                ],
                "service": "如果重建地图和清洁传感器后仍持续漏扫，建议联系售后检查传感器或驱动轮组件。",
            },
            {
                "keywords": ["不充电", "充不上电", "无法充电", "充电失败", "电池"],
                "name": "不充电或充电失败",
                "risk_level": "高",
                "causes": [
                    "充电座电源未接好或插座无电",
                    "机器人和充电座金属触点有灰尘、氧化或污渍",
                    "机器人未正确对准充电座",
                    "电池老化或充电模块异常",
                ],
                "steps": [
                    "确认充电座电源线、适配器和插座正常供电",
                    "用干布清洁机器人底部和充电座上的金属触点",
                    "将机器人手动放回充电座，确认触点贴合且指示灯正常",
                    "重启机器人后再次尝试充电，并观察是否反复失败",
                ],
                "service": "如果清洁触点和更换插座后仍无法充电，建议售后检测电池或充电模块。",
            },
            {
                "keywords": ["异响", "噪音", "声音大", "吱吱", "咔咔", "摩擦声"],
                "name": "运行异响或噪音异常",
                "risk_level": "中",
                "causes": [
                    "主刷、边刷、万向轮或驱动轮缠绕毛发和异物",
                    "尘盒、滤网或主刷盖未安装到位",
                    "地面颗粒物较大导致滚刷摩擦声增大",
                    "电机、风机或轮组存在机械异常",
                ],
                "steps": [
                    "关闭电源后拆下主刷、边刷和万向轮，清理毛发、线头和硬物",
                    "检查尘盒、滤网、主刷盖是否安装牢固",
                    "切换到安静模式测试噪音是否明显降低",
                    "让机器人在空旷硬地运行，判断异响是否仍然存在",
                ],
                "service": "如果清理滚刷和轮组后仍有持续尖锐异响，建议售后检测风机、电机或轮组。",
            },
            {
                "keywords": ["拖布不出水", "不出水", "出水少", "拖地没水", "水箱"],
                "name": "拖布不出水或出水不足",
                "risk_level": "中",
                "causes": [
                    "水箱未安装到位或水量不足",
                    "出水口堵塞，拖布安装过紧或过脏",
                    "App 中水量档位设置过低",
                    "电子水泵或水箱识别组件异常",
                ],
                "steps": [
                    "取下水箱重新加水并安装到位，确认水箱卡扣闭合",
                    "清洗拖布，检查出水口是否被水垢或杂质堵塞",
                    "在 App 中将出水量调到中档或高档后再次测试",
                    "更换干净拖布并运行短程拖地任务，观察是否恢复出水",
                ],
                "service": "如果水箱安装和出水口清洁后仍不出水，建议售后检测水泵或水箱识别模块。",
            },
            {
                "keywords": ["无法回充", "回不了充", "回充失败", "找不到基站", "找不到充电座"],
                "name": "无法回充或找不到基站",
                "risk_level": "高",
                "causes": [
                    "基站周围空间不足或附近有反光、遮挡物",
                    "基站位置被移动，地图中的基站坐标失效",
                    "机器人电量过低或路径被障碍物阻断",
                    "回充传感器、红外窗口或地图定位异常",
                ],
                "steps": [
                    "确保基站左右和前方留出足够空间，移除周围障碍物",
                    "不要频繁移动基站，如已移动，建议重新建图或更新地图",
                    "清洁机器人和基站上的红外窗口、传感器区域",
                    "从基站出发执行一次完整清扫，再观察能否自动回充",
                ],
                "service": "如果固定基站位置并重建地图后仍频繁回充失败，建议售后检查回充传感器或定位模块。",
            },
        ]

        matched_rule = None
        for rule in fault_rules:
            if any(keyword in issue_text for keyword in rule["keywords"]):
                matched_rule = rule
                break

        if not matched_rule:
            matched_rule = {
                "name": "通用故障",
                "risk_level": "待确认",
                "causes": [
                    "设备状态、传感器、耗材或地图设置可能存在异常",
                    "故障现象描述还不够具体，需要结合设备状态进一步判断",
                ],
                "steps": [
                    "先重启机器人并确认电量充足",
                    "检查主刷、边刷、滤网、尘盒、水箱和传感器是否正常",
                    "查看 App 是否有错误码或异常提示",
                    "如问题和清扫路径有关，尝试更新地图或重新建图",
                ],
                "service": "如果重启和基础清洁后仍重复出现，建议联系售后进一步检测。",
            }

        rag_reference = ""
        try:
            rag_reference = rag.rag_summarize(f"{issue_text} 故障排查 维修 保养", with_sources=True)
        except Exception as e:
            logger.warning(f"[diagnose_fault]RAG检索失败: {str(e)}")
            rag_reference = "知识库参考暂时不可用，以下为基于故障关键词的初步诊断。"
        rag_reference = _remove_reference_sources(rag_reference)
        rag_has_reference = "知识库中未检索到足够资料" not in rag_reference and "暂时不可用" not in rag_reference

        device_context = "未提供用户ID，暂未关联具体设备状态。"
        device_insights = []
        device_risk_signals = []
        if user_id:
            device = find_first_csv_row("data/external/devices.csv", user_id=user_id)
            if device:
                error_code = device.get("last_error_code") or "无"
                error_message = device.get("last_error_message") or "当前未记录异常"
                battery_percent = _safe_int(device.get("battery_percent"), 0) or 0
                device_context = (
                    f"设备{device.get('device_id', '未知')}，型号{device.get('model', '未知')}，"
                    f"电量{device.get('battery_percent', '未知')}%，"
                    f"在线状态{device.get('online_status', '未知')}，"
                    f"基站状态{device.get('dock_status', '未知')}，"
                    f"最近异常：{error_code}，{error_message}。"
                )
                if device.get("online_status") == "offline":
                    device_insights.append("设备当前离线，需优先确认电源、网络连接和基站供电。")
                    device_risk_signals.append("offline")
                if battery_percent < 20:
                    device_insights.append("设备电量低于20%，可能影响回充、续扫或任务完成。")
                    device_risk_signals.append("low_battery")
                if error_code != "无":
                    device_insights.append(f"设备存在最近异常记录：{error_code}，{error_message}。")
                    device_risk_signals.append("device_error")
                if "回充" in issue_text and device.get("dock_status") in ["undocked", "returning"]:
                    device_insights.append("当前基站状态与回充问题相关，建议重点检查基站位置、触点和回充传感器。")
            else:
                device_context = f"未查询到用户{user_id}绑定的设备。"
        else:
            device_insights.append("未提供用户ID，无法结合设备电量、在线状态和错误码进一步判断。")

        history_context = "未提供用户ID，暂未关联清扫历史。"
        history_insights = []
        if user_id:
            history_rows = [
                row for row in read_csv_rows("data/external/cleaning_history.csv")
                if row.get("user_id") == user_id
            ]
            if history_rows:
                sorted_rows = sorted(
                    history_rows,
                    key=lambda row: f"{row.get('cleaning_date', '')} {row.get('start_time', '')}",
                    reverse=True,
                )
                recent_rows = sorted_rows[:3]
                total_errors = sum(_safe_int(row.get("error_count"), 0) or 0 for row in recent_rows)
                low_coverage_rows = [
                    row for row in recent_rows
                    if (_safe_int(row.get("coverage_percent"), 100) or 100) < 80
                ]
                missed_rows = [
                    row for row in recent_rows
                    if row.get("missed_spots") and row.get("missed_spots") not in ["无", "none"]
                ]
                recent_summary = "；".join(
                    f"{row.get('cleaning_date', '未知日期')}覆盖率{row.get('coverage_percent', '未知')}%，"
                    f"异常{row.get('error_count', '0')}次，漏扫点{row.get('missed_spots', '无')}"
                    for row in recent_rows
                )
                history_context = f"最近{len(recent_rows)}次清扫记录：{recent_summary}。"
                if total_errors > 0:
                    history_insights.append(f"最近清扫记录中累计出现{total_errors}次异常，说明问题可能不是偶发。")
                if low_coverage_rows:
                    history_insights.append("最近存在覆盖率低于80%的记录，需关注地图、障碍物和定位状态。")
                if missed_rows:
                    history_insights.append("最近记录中存在漏扫点，可结合地面障碍物、地图分区和传感器清洁情况排查。")
                if not history_insights:
                    history_insights.append("最近清扫历史未显示明显连续异常，可先按单次故障进行基础排查。")
            else:
                history_context = f"未查询到用户{user_id}的清扫历史记录。"

        risk_level = matched_rule["risk_level"]
        if "device_error" in device_risk_signals or ("无法回充" in issue_text and "low_battery" in device_risk_signals):
            risk_level = "高"
        elif risk_level == "待确认" and (device_insights or history_insights):
            risk_level = "中"

        service_recommended = risk_level == "高" or "device_error" in device_risk_signals
        if matched_rule["risk_level"] == "待确认" and not rag_has_reference and not user_id:
            service_recommended = False
        service_text = "建议售后" if service_recommended else "暂不一定需要售后"

        supplemental_notes = []
        if not rag_has_reference:
            supplemental_notes.append("知识库中未检索到足够资料，当前诊断主要基于本地设备/历史数据和内置故障规则。")
        if matched_rule["risk_level"] == "待确认":
            supplemental_notes.append("故障现象还不够具体，建议补充错误码、发生频率、是否伴随异响/卡住/无法回充等细节。")
        supplemental_notes.extend(device_insights)
        supplemental_notes.extend(history_insights)
        if not supplemental_notes:
            supplemental_notes.append("诊断依据来自知识库资料、故障关键词和当前用户设备/清扫数据。")

        next_actions = [
            "先按排查步骤完成基础检查，并记录故障是否复现。",
            "若 App 有错误码，请补充错误码、出现时间和故障发生场景，便于进一步定位。",
        ]
        if service_recommended:
            next_actions.append(matched_rule["service"])
        else:
            next_actions.append("如果完成基础排查后仍连续复现，再联系售后进一步检测。")

        diagnosis = {
            "fault_type": matched_rule["name"],
            "issue": issue_text,
            "user_id": user_id or "未提供",
            "risk_level": risk_level,
            "service_recommended": service_text,
            "device_context": device_context,
            "history_context": history_context,
            "causes": matched_rule["causes"],
            "steps": matched_rule["steps"],
            "next_actions": next_actions,
            "supplemental_notes": supplemental_notes,
        }

        return (
            f"故障类型：{diagnosis['fault_type']}\n"
            f"用户描述：{diagnosis['issue']}\n"
            f"关联用户：{diagnosis['user_id']}\n"
            f"关联设备状态：{diagnosis['device_context']}\n"
            f"关联清扫历史：{diagnosis['history_context']}\n"
            "可能原因：\n"
            f"{_format_bullets(diagnosis['causes'])}\n"
            "排查步骤：\n"
            f"{_format_numbered_steps(diagnosis['steps'])}\n"
            f"风险等级：{diagnosis['risk_level']}\n"
            f"是否建议售后：{diagnosis['service_recommended']}\n"
            "下一步建议：\n"
            f"{_format_bullets(diagnosis['next_actions'])}\n"
            "诊断依据：\n"
            f"{_format_bullets(diagnosis['supplemental_notes'])}"
        )
    except Exception as e:
        logger.exception(f"[diagnose_fault]故障诊断失败: {str(e)}")
        return "故障诊断过程中出现异常，请稍后重试，并补充具体故障现象、用户ID或设备错误码。"

@tool(description="获取指定城市的天气，以消息字符串的形式返回")
def get_weather(city: str) -> str:
    return f"城市{city}天气为晴天，气温26摄氏度，空气湿度50%，南风1级，AQI21，最近6小时降雨概率极低"


@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() -> str:
    return random.choice(["深圳", "合肥", "杭州"])


@tool(description="获取当前会话默认用户ID，以纯字符串形式返回")
def get_user_id() -> str:
    return current_user_id


@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() -> str:
    return random.choice(month_arr)

def generate_external_data():
    """
    {
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        ...
    }
    :return:
    """
    if not external_data:
        external_data_path = get_abs_path(agent_conf['external_data_path'])

        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f'外部数据文件{external_data_path}不存在')

        with open(external_data_path,'r',encoding='utf-8') as f:
            for line in f.readlines()[1:]:
                arr: list[str] = line.strip().split(",")

                user_id: str = arr[0].replace('"', "")
                feature: str = arr[1].replace('"', "")
                efficiency: str = arr[2].replace('"', "")
                consumables: str = arr[3].replace('"', "")
                comparison: str = arr[4].replace('"', "")
                time: str = arr[5].replace('"', "")

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    '特征': feature,
                    '效率': efficiency,
                    '消耗': consumables,
                    '对比': comparison,
                }

@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回， 如果未检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()
    try:
        return  external_data[user_id][month]
    except KeyError:
        logger.warning(f'[fetch_external_data]未能检索到用户: {user_id}在{month}的使用记录数据')
        return ''

@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return 'fill_context_for_report已调用'
