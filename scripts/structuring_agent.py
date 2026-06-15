from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common import copy_demo, now, read_json, write_json


SCHEMA_KEYS = [
    "competitor_name",
    "product_positioning",
    "target_users",
    "use_cases",
    "core_features",
    "ai_capabilities",
    "pricing_model",
    "business_model",
    "user_feedback",
    "strengths",
    "weaknesses",
    "recent_updates",
    "source_links",
    "update_time",
    "confidence_level",
    "missing_fields",
    "conflict_flags",
]

DEFAULT_ROW = {
    "competitor_name": "",
    "product_positioning": "待确认",
    "target_users": "待确认",
    "use_cases": [],
    "core_features": [],
    "ai_capabilities": [],
    "pricing_model": "待确认",
    "business_model": "待确认",
    "user_feedback": [],
    "strengths": [],
    "weaknesses": [],
    "recent_updates": [],
    "source_links": [],
    "update_time": "",
    "confidence_level": "low",
    "missing_fields": [],
    "conflict_flags": [],
}


def run(output_dir: Path, clients: dict[str, Any], demo_mode: bool) -> dict[str, Any]:
    if demo_mode:
        copy_demo("structured_schema_table.json", output_dir)
        return read_json(output_dir / "structured_schema_table.json", {})

    collected = read_json(output_dir / "collected_sources.json", {})
    llm = clients["llm"]
    schema_table = []
    if not llm.demo_mode:
        prompt = (
            "请把以下竞品公开资料整理为统一竞品知识 Schema。"
            "所有不确定内容必须写为“待确认”或加入 missing_fields，不得写成事实。"
            "必须输出如下 JSON："
            "{"
            "\"schema_table\":[{"
            "\"competitor_name\":\"\","
            "\"product_positioning\":\"\","
            "\"target_users\":\"\","
            "\"use_cases\":[],"
            "\"core_features\":[],"
            "\"ai_capabilities\":[],"
            "\"pricing_model\":\"\","
            "\"business_model\":\"\","
            "\"user_feedback\":[],"
            "\"strengths\":[],"
            "\"weaknesses\":[],"
            "\"recent_updates\":[],"
            "\"source_links\":[],"
            "\"update_time\":\"\","
            "\"confidence_level\":\"high / medium / low\","
            "\"missing_fields\":[],"
            "\"conflict_flags\":[]"
            "}]}"
            f"\n资料：{collected}"
        )
        generated = llm.generate_json(prompt, {"schema_table": [DEFAULT_ROW]})
        schema_table = _normalize_rows(generated.get("schema_table", []), collected)
    if not schema_table:
        schema_table = [_heuristic_row(item) for item in collected.get("competitors", [])]

    result = {
        "agent": "structuring",
        "status": "completed",
        "schema_table": schema_table,
        "field_completion_matrix": [
            {
                "competitor": row["competitor_name"],
                "completed": len([key for key in SCHEMA_KEYS if row.get(key) and key not in {"missing_fields", "conflict_flags"}]),
                "missing": len(row.get("missing_fields", [])),
            }
            for row in schema_table
        ],
        "missing_field_flags": sorted({field for row in schema_table for field in row.get("missing_fields", [])}),
        "conflict_flags": sorted({field for row in schema_table for field in row.get("conflict_flags", [])}),
        "handoff_to_next_agent": {
            "next_agent": "comparing",
            "materials": ["结构化竞品知识表", "字段完成情况", "缺失字段", "冲突信息", "待确认内容"],
        },
    }
    write_json(output_dir / "structured_schema_table.json", result)
    return result


def _heuristic_row(item: dict[str, Any]) -> dict[str, Any]:
    name = item.get("name", "")
    packets = item.get("source_packets", [])
    supported = {field for packet in packets for field in packet.get("fields_supported", [])}
    missing = item.get("missing_information", [])
    return {
        "competitor_name": name,
        "product_positioning": _text_for(name, "产品定位", packets),
        "target_users": "公开资料中未完整说明，需结合目标市场确认",
        "use_cases": ["会议协作", "内容总结", "团队知识沉淀"],
        "core_features": ["智能摘要", "协作沉淀"] if "core_features" in supported else ["待确认"],
        "ai_capabilities": ["摘要", "生成", "问答"] if "ai_capabilities" in supported else ["待确认"],
        "pricing_model": "公开价格口径待确认" if "价格模式" in missing else "公开资料可支持初步判断",
        "business_model": "企业协作或订阅增值",
        "user_feedback": ["公开用户反馈样本不足"] if "用户反馈" in missing else ["公开评论可作为弱信号"],
        "strengths": ["公开资料显示具备场景能力"],
        "weaknesses": missing,
        "recent_updates": ["近期动态需结合更新日志确认"],
        "source_links": [packet.get("url", "") for packet in packets],
        "update_time": now(),
        "confidence_level": "medium" if len(missing) <= 1 else "low",
        "missing_fields": missing,
        "conflict_flags": [],
    }


def _normalize_rows(rows: Any, collected: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    competitor_names = [item.get("name", "") for item in collected.get("competitors", [])]
    normalized = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        full = {**DEFAULT_ROW, **row}
        if not full.get("competitor_name") and index < len(competitor_names):
            full["competitor_name"] = competitor_names[index]
        if not full.get("competitor_name"):
            continue
        missing = set(full.get("missing_fields") or [])
        for key in SCHEMA_KEYS:
            if key not in full:
                full[key] = DEFAULT_ROW.get(key, "待确认")
            if key in {"use_cases", "core_features", "ai_capabilities", "user_feedback", "strengths", "weaknesses", "recent_updates", "source_links", "missing_fields", "conflict_flags"}:
                if not isinstance(full[key], list):
                    full[key] = [str(full[key])] if full[key] else []
            elif not full[key] and key not in {"missing_fields", "conflict_flags"}:
                full[key] = "待确认"
                missing.add(key)
        if full.get("confidence_level") not in {"high", "medium", "low"}:
            full["confidence_level"] = "low"
        full["missing_fields"] = sorted(missing)
        normalized.append(full)
    return normalized


def _text_for(name: str, field: str, packets: list[dict[str, Any]]) -> str:
    excerpt = "；".join(packet.get("excerpt", "")[:80] for packet in packets[:2])
    return f"{name} 的{field}基于公开资料整理：{excerpt}" if excerpt else "公开资料不足，待确认"
