from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from scripts.common import copy_demo, read_json, write_json


def run(output_dir: Path, clients: dict[str, Any], demo_mode: bool) -> dict[str, Any]:
    if demo_mode:
        copy_demo("quality_report.json", output_dir)
        copy_demo("competitive_report_final.md", output_dir)
        return read_json(output_dir / "quality_report.json", {})

    report_path = output_dir / "report_draft.md"
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    structured = read_json(output_dir / "structured_schema_table.json", {})
    comparison = read_json(output_dir / "comparison_analysis.json", {})
    collected = read_json(output_dir / "collected_sources.json", {})
    llm = clients["llm"]
    result = {}
    if not llm.demo_mode:
        try:
            result = _llm_quality_check(llm, report, structured, comparison, collected)
        except Exception:
            result = {}
    if not result:
        result = _rule_quality_check(report, structured, comparison, collected)
    result = _normalize_quality(result, report, output_dir)
    write_json(output_dir / "quality_report.json", result)
    return result


def _llm_quality_check(llm, report: str, structured: dict[str, Any], comparison: dict[str, Any], collected: dict[str, Any]) -> dict[str, Any]:
    prompt = (
        "你是严格的竞品分析质检 Agent。请检查：来源完整性、字段一致性、结论支撑关系、推断跳跃、"
        "风险边界是否充分、是否存在无来源强判断。"
        "如果出现“用户体验较差”“价格最高”“市场领先”等没有证据的强判断，必须加入 rejected_claims，并要求改为弱表述。"
        "必须输出 JSON，结构包含 agent、status、passed、overall_score、issues、rejected_claims、rollback_needed、rollback_target、final_report_path。"
        f"\n报告初稿：{report}"
        f"\n结构化表：{structured}"
        f"\n对比分析：{comparison}"
        f"\n采集来源：{collected}"
    )
    return llm.generate_json(
        prompt,
        {
            "agent": "quality",
            "status": "completed",
            "passed": True,
            "overall_score": 0,
            "issues": [
                {
                    "severity": "critical / major / minor",
                    "category": "source_missing / field_conflict / weak_evidence / logic_gap / formatting",
                    "description": "",
                    "location": "",
                    "suggestion": "",
                    "rollback_target": "collecting / structuring / comparing / writing / none",
                }
            ],
            "rejected_claims": [{"original_claim": "", "reason": "", "revised_claim": ""}],
            "rollback_needed": False,
            "rollback_target": "",
            "final_report_path": "",
        },
    )


def _rule_quality_check(report: str, structured: dict[str, Any], comparison: dict[str, Any], collected: dict[str, Any]) -> dict[str, Any]:
    issues = []
    if "风险" not in report:
        issues.append(_issue("major", "logic_gap", "报告缺少风险边界说明。", "风险与信息缺口", "补充风险边界。", "writing"))
    if structured.get("missing_field_flags"):
        issues.append(_issue("minor", "field_conflict", "存在缺失字段，需要在报告中说明。", "结构化竞品知识表", "保留字段缺失说明。", "none"))
    if not collected.get("competitors"):
        issues.append(_issue("critical", "source_missing", "缺少来源资料。", "来源清单", "回退信息采集。", "collecting"))

    rejected_claims = _detect_strong_claims(report)
    if rejected_claims:
        issues.append(_issue("major", "weak_evidence", "报告存在缺少来源支撑的强判断。", "核心发现", "改为弱表述或补充来源。", "writing"))
    passed = not any(issue["severity"] == "critical" for issue in issues)
    score = max(60, 92 - len(issues) * 8)
    rollback_target = next((issue["rollback_target"] for issue in issues if issue["rollback_target"] != "none"), "")
    return {
        "agent": "quality",
        "status": "completed",
        "passed": passed,
        "overall_score": score,
        "issues": issues,
        "rejected_claims": rejected_claims,
        "rollback_needed": not passed,
        "rollback_target": rollback_target,
        "final_report_path": "",
        "comparison_summary": comparison.get("common_patterns", []),
    }


def _normalize_quality(result: dict[str, Any], report: str, output_dir: Path) -> dict[str, Any]:
    issues = result.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    normalized_issues = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        normalized_issues.append(
            {
                "severity": issue.get("severity") if issue.get("severity") in {"critical", "major", "minor"} else "minor",
                "category": issue.get("category") if issue.get("category") in {"source_missing", "field_conflict", "weak_evidence", "logic_gap", "formatting"} else "logic_gap",
                "description": issue.get("description", "待确认问题"),
                "location": issue.get("location", "报告初稿"),
                "suggestion": issue.get("suggestion", "补充证据或改为弱表述"),
                "rollback_target": issue.get("rollback_target") if issue.get("rollback_target") in {"collecting", "structuring", "comparing", "writing", "none"} else "none",
            }
        )
    rejected_claims = result.get("rejected_claims", [])
    if not isinstance(rejected_claims, list):
        rejected_claims = []
    detected = _detect_strong_claims(report)
    existing_claims = {item.get("original_claim") for item in rejected_claims if isinstance(item, dict)}
    for item in detected:
        if item["original_claim"] not in existing_claims:
            rejected_claims.append(item)
            normalized_issues.append(_issue("major", "weak_evidence", "报告存在缺少来源支撑的强判断。", "核心发现", "改为弱表述或补充来源。", "writing"))
    passed = bool(result.get("passed", True)) and not any(issue["severity"] == "critical" for issue in normalized_issues)
    rollback_target = result.get("rollback_target") or next((issue["rollback_target"] for issue in normalized_issues if issue["rollback_target"] != "none"), "")
    final_path = output_dir / "competitive_report_final.md"
    report_path = output_dir / "report_draft.md"
    if report_path.exists():
        shutil.copyfile(report_path, final_path)
    return {
        "agent": "quality",
        "status": "completed",
        "passed": passed,
        "overall_score": int(result.get("overall_score") or max(60, 92 - len(normalized_issues) * 8)),
        "issues": normalized_issues,
        "rejected_claims": rejected_claims,
        "rollback_needed": bool(result.get("rollback_needed", False)) or any(issue["severity"] == "critical" for issue in normalized_issues),
        "rollback_target": rollback_target,
        "final_report_path": str(final_path),
    }


def _detect_strong_claims(report: str) -> list[dict[str, str]]:
    patterns = ["用户体验较差", "用户体验较弱", "价格最高", "市场领先", "绝对领先", "最佳选择"]
    rejected = []
    for pattern in patterns:
        if pattern in report:
            rejected.append(
                {
                    "original_claim": pattern,
                    "reason": "缺少足够来源或结构化字段支撑，属于强判断。",
                    "revised_claim": f"公开资料暂不足以直接判断“{pattern}”，建议改为弱表述或补充来源。",
                }
            )
    return rejected


def _issue(severity: str, category: str, description: str, location: str, suggestion: str, rollback_target: str) -> dict[str, str]:
    return {
        "severity": severity,
        "category": category,
        "description": description,
        "location": location,
        "suggestion": suggestion,
        "rollback_target": rollback_target,
    }
