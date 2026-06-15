from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common import copy_demo, write_json


def run(task: dict[str, Any], output_dir: Path, clients: dict[str, Any], demo_mode: bool) -> dict[str, Any]:
    if demo_mode:
        copy_demo("planning_result.json", output_dir)
        return _load_demo(output_dir)

    competitors = task.get("target_companies", [])[:6]
    dimensions = task.get("dimensions", [])[:10]
    source_scope = task.get("source_scope", [])
    clarification_questions = []
    if not task.get("report_usage"):
        clarification_questions.append("请补充报告用途，以便确定分析深度和表达口径。")
    if not dimensions:
        clarification_questions.append("请补充重点分析维度，例如产品定位、核心功能、AI 能力、价格模式。")
    scope_risk = ""
    if len(competitors) > 5:
        scope_risk = "竞品数量偏多，建议收窄到 3-5 个代表性竞品，或按细分赛道分组。"

    result = {
        "agent": "planning",
        "status": "completed",
        "analysis_goal": f"围绕 {task['industry']} 形成用于{task.get('report_usage') or '产品决策'}的竞品分析报告。",
        "competitor_scope": competitors,
        "dimension_list": dimensions,
        "source_scope": source_scope,
        "clarification_needed": bool(clarification_questions),
        "clarification_questions": clarification_questions,
        "scope_risk": scope_risk,
        "handoff_to_next_agent": {
            "next_agent": "collecting",
            "materials": ["竞品名单", "搜索关键词", "分析维度", "信息来源范围", "需要优先确认的问题"],
        },
    }
    write_json(output_dir / "planning_result.json", result)
    return result


def _load_demo(output_dir: Path) -> dict[str, Any]:
    import json
    with (output_dir / "planning_result.json").open("r", encoding="utf-8") as file:
        return json.load(file)
