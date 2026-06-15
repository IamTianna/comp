from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common import copy_demo, read_json, write_json


def run(output_dir: Path, clients: dict[str, Any], demo_mode: bool) -> dict[str, Any]:
    if demo_mode:
        copy_demo("comparison_analysis.json", output_dir)
        return read_json(output_dir / "comparison_analysis.json", {})

    structured = read_json(output_dir / "structured_schema_table.json", {})
    rows = structured.get("schema_table", [])
    llm = clients["llm"]
    if not llm.demo_mode:
        prompt = (
            "请基于结构化竞品知识表输出多维对比、行业共性、关键差异、机会点和分析风险。"
            "比较结论必须区分事实、推断和建议，避免强断言。"
            "必须输出 JSON，包含 comparison_matrix、common_patterns、key_differences、opportunity_points、analysis_risks。"
            "每个 opportunity_points 项必须包含 opportunity、evidence、logic、confidence、risk。"
            f"\n结构化表：{structured}"
        )
        generated = llm.generate_json(
            prompt,
            {
                "comparison_matrix": [],
                "common_patterns": [],
                "key_differences": [],
                "opportunity_points": [{"opportunity": "", "evidence": [], "logic": "", "confidence": "medium", "risk": ""}],
                "analysis_risks": [],
            },
        )
        generated = _normalize_analysis(generated)
        if generated:
            generated["agent"] = "comparing"
            generated["status"] = "completed"
            generated["handoff_to_next_agent"] = {
                "next_agent": "writing",
                "materials": ["多维度对比矩阵", "行业共性", "关键差异", "初步机会点", "分析风险"],
            }
            write_json(output_dir / "comparison_analysis.json", generated)
            return generated

    result = {
        "agent": "comparing",
        "status": "completed",
        "comparison_matrix": [
            {"dimension": "核心功能", **{row["competitor_name"]: "、".join(row.get("core_features", [])) for row in rows}},
            {"dimension": "AI能力", **{row["competitor_name"]: "、".join(row.get("ai_capabilities", [])) for row in rows}},
            {"dimension": "商业模式", **{row["competitor_name"]: row.get("business_model", "") for row in rows}},
        ],
        "common_patterns": ["AI 摘要和内容沉淀成为基础能力", "协作上下文连接影响产品差异"],
        "key_differences": [f"{row['competitor_name']}：{row.get('product_positioning', '')}" for row in rows],
        "opportunity_points": [
            {
                "opportunity": "会议待办自动沉淀",
                "evidence": [row["competitor_name"] for row in rows if "摘要" in " ".join(row.get("ai_capabilities", []))],
                "logic": "会议内容进入任务流程可以降低会后跟进成本。",
                "confidence": "medium",
                "risk": "需要真实用户访谈验证。",
            }
        ],
        "analysis_risks": structured.get("missing_field_flags", []) + structured.get("conflict_flags", []),
        "handoff_to_next_agent": {
            "next_agent": "writing",
            "materials": ["多维度对比矩阵", "行业共性", "关键差异", "初步机会点", "分析风险"],
        },
    }
    write_json(output_dir / "comparison_analysis.json", result)
    return result


def _normalize_analysis(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    required = ["comparison_matrix", "common_patterns", "key_differences", "opportunity_points", "analysis_risks"]
    if not any(key in data for key in required):
        return {}
    normalized = {key: data.get(key, []) if isinstance(data.get(key, []), list) else [] for key in required}
    risks = list(normalized["analysis_risks"])
    points = []
    for raw in normalized["opportunity_points"]:
        if not isinstance(raw, dict):
            continue
        point = {
            "opportunity": raw.get("opportunity", "待确认机会点"),
            "evidence": raw.get("evidence", []) if isinstance(raw.get("evidence", []), list) else [str(raw.get("evidence"))],
            "logic": raw.get("logic", "待确认"),
            "confidence": raw.get("confidence", "medium"),
            "risk": raw.get("risk", "待确认"),
        }
        if not point["evidence"]:
            point["confidence"] = "low"
            risk = f"机会点「{point['opportunity']}」缺少 evidence，已降级为 low。"
            point["risk"] = point["risk"] if point["risk"] != "待确认" else risk
            risks.append(risk)
        if point["confidence"] not in {"high", "medium", "low"}:
            point["confidence"] = "low"
        points.append(point)
    normalized["opportunity_points"] = points
    normalized["analysis_risks"] = risks
    return normalized
