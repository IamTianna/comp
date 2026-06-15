from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.run_manager import LOGS_ROOT, OUTPUT_ROOT, RunManager, safe_child


AGENT_FILES = {
    "planning": ("planning_result.json", "json"),
    "collecting": ("collected_sources.json", "json"),
    "structuring": ("structured_schema_table.json", "json"),
    "comparing": ("comparison_analysis.json", "json"),
    "writing": ("report_draft.md", "markdown"),
    "quality": ("quality_report.json", "json"),
}


def load_status(run_id: str) -> dict[str, Any]:
    path = safe_child(LOGS_ROOT, run_id, "status.json")
    return RunManager.read_json(path, default={})


def load_logs(run_id: str) -> list[dict[str, Any]]:
    path = safe_child(LOGS_ROOT, run_id, "pipeline.json")
    return RunManager.read_json(path, default=[])


def load_agent_artifact(run_id: str, agent_id: str) -> tuple[str, Any]:
    if agent_id not in AGENT_FILES:
        raise KeyError(f"Unknown agent: {agent_id}")
    filename, content_type = AGENT_FILES[agent_id]
    path = safe_child(OUTPUT_ROOT, run_id, filename)
    if content_type == "markdown":
        data = path.read_text(encoding="utf-8") if path.exists() else ""
    else:
        data = RunManager.read_json(path, default={})
    return content_type, data


def load_result(run_id: str) -> dict[str, Any]:
    output_dir = safe_child(OUTPUT_ROOT, run_id)
    result = RunManager.read_json(output_dir / "result.json", default={})
    final_report = output_dir / "competitive_report_final.md"
    if final_report.exists():
        result["final_report_markdown"] = final_report.read_text(encoding="utf-8")
    return result


def list_artifacts(run_id: str) -> dict[str, list[str]]:
    output_dir = safe_child(OUTPUT_ROOT, run_id)
    log_dir = safe_child(LOGS_ROOT, run_id)
    return {
        "output": [str(path.relative_to(OUTPUT_ROOT.parent)) for path in sorted(output_dir.glob("*")) if path.is_file()],
        "logs": [str(path.relative_to(LOGS_ROOT.parent)) for path in sorted(log_dir.glob("*")) if path.is_file()],
    }
