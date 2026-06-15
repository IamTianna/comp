from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common import copy_demo, markdown_from_sources, read_json, write_json


def run(output_dir: Path, clients: dict[str, Any], demo_mode: bool) -> dict[str, Any]:
    if demo_mode:
        copy_demo("report_draft.md", output_dir)
        copy_demo("report_metadata.json", output_dir)
        return read_json(output_dir / "report_metadata.json", {})

    structured = read_json(output_dir / "structured_schema_table.json", {})
    comparison = read_json(output_dir / "comparison_analysis.json", {})
    llm = clients["llm"]
    if not llm.demo_mode:
        prompt = (
            "请根据结构化表和对比分析生成 Markdown 竞品分析报告。"
            "每条核心发现必须包含：依据、可信度（high / medium / low）、风险边界。"
            "必须写入“风险与信息缺口”章节，包含 comparison_analysis.analysis_risks。"
            "禁止输出没有来源支撑的战略结论。"
        )
        report = llm.generate_text(f"{prompt}\n结构化表：{structured}\n对比分析：{comparison}")
    else:
        report = _fallback_report(structured, comparison)
    report = _ensure_traceability(report, comparison)
    (output_dir / "report_draft.md").write_text(report, encoding="utf-8")
    evidence_chains = _build_evidence_chains(comparison, structured)
    metadata = {
        "agent": "writing",
        "status": "completed",
        "draft_report_path": str(output_dir / "report_draft.md"),
        "report_sections": ["执行摘要", "分析目标与范围", "竞品概览", "多维度对比矩阵", "核心发现", "产品机会点", "风险与信息缺口", "初步建议", "来源清单"],
        "evidence_chains": evidence_chains,
        "risk_disclosures": comparison.get("analysis_risks", []),
        "handoff_to_next_agent": {
            "next_agent": "quality",
            "materials": ["报告初稿", "核心发现", "机会点证据链", "风险与信息缺口", "来源清单"],
        },
    }
    write_json(output_dir / "report_metadata.json", metadata)
    return metadata


def _fallback_report(structured: dict[str, Any], comparison: dict[str, Any]) -> str:
    competitors = [row.get("competitor_name", "") for row in structured.get("schema_table", [])]
    opportunities = "\n".join(
        f"- {item.get('opportunity')}: {item.get('logic')}\n"
        f"  - 依据：{'；'.join(item.get('evidence', [])) or '待确认'}\n"
        f"  - 可信度：{item.get('confidence', 'low')}\n"
        f"  - 风险边界：{item.get('risk', '待确认')}"
        for item in comparison.get("opportunity_points", [])
    )
    risks = "\n".join(f"- {risk}" for risk in comparison.get("analysis_risks", [])) or "- 暂无"
    return markdown_from_sources(
        "竞品分析报告",
        [
            ("1. 执行摘要", "本报告基于公开资料、结构化字段和对比分析生成，所有结论均保留风险边界。"),
            ("2. 分析目标与范围", f"竞品范围：{', '.join(competitors)}。"),
            ("3. 竞品概览", "\n".join(f"- {name}" for name in competitors)),
            ("4. 多维度对比矩阵", str(comparison.get("comparison_matrix", []))),
            (
                "5. 核心发现",
                "\n".join(
                    f"- {item}\n  - 依据：结构化字段与公开来源交叉支持\n  - 可信度：medium\n  - 风险边界：需要真实用户访谈和业务数据进一步验证"
                    for item in comparison.get("common_patterns", [])
                ),
            ),
            ("6. 产品机会点", opportunities),
            ("7. 风险与信息缺口", risks),
            ("8. 初步建议", "优先验证证据链较完整、实现难度可控的机会点。"),
            ("9. 来源清单", "详见 collected_sources.json 与 structured_schema_table.json。"),
        ],
    )


def _ensure_traceability(report: str, comparison: dict[str, Any]) -> str:
    additions = []
    if "依据：" not in report or "可信度：" not in report or "风险边界：" not in report:
        additions.append("## 核心结论证据链")
        for item in comparison.get("opportunity_points", []):
            additions.append(
                f"- {item.get('opportunity', '待确认机会点')}\n"
                f"  - 依据：{'；'.join(item.get('evidence', [])) or '待确认'}\n"
                f"  - 可信度：{item.get('confidence', 'low')}\n"
                f"  - 风险边界：{item.get('risk', '待确认')}"
            )
    if comparison.get("analysis_risks") and "风险与信息缺口" not in report:
        additions.append("## 风险与信息缺口")
        additions.extend(f"- {risk}" for risk in comparison.get("analysis_risks", []))
    return report.rstrip() + ("\n\n" + "\n".join(additions) if additions else "") + "\n"


def _build_evidence_chains(comparison: dict[str, Any], structured: dict[str, Any]) -> list[dict[str, Any]]:
    source_links = {
        row.get("competitor_name"): row.get("source_links", [])
        for row in structured.get("schema_table", [])
        if isinstance(row, dict)
    }
    all_links = [link for links in source_links.values() for link in links]
    chains = []
    for item in comparison.get("opportunity_points", []):
        evidence = item.get("evidence", [])
        chains.append(
            {
                "claim": item.get("opportunity", ""),
                "evidence": evidence,
                "source_links": all_links[:8],
                "confidence": item.get("confidence", "low"),
                "risk_boundary": item.get("risk", "待确认"),
            }
        )
    return chains
