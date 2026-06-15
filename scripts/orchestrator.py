from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.clients.fetch_client import FetchClient
from backend.clients.llm_client import LLMClient
from backend.clients.search_client import SearchClient
from backend.services.run_manager import RunManager, new_run_id
from scripts import collecting_agent, comparing_agent, planning_agent, quality_agent, structuring_agent, writing_agent
from scripts.common import read_json, write_json


PHASES = [
    ("planning", "任务规划 Agent", 10, 18),
    ("collecting", "信息采集 Agent", 24, 38),
    ("structuring", "结构化处理 Agent", 44, 58),
    ("comparing", "对比分析 Agent", 64, 74),
    ("writing", "报告撰写 Agent", 80, 88),
    ("quality", "质检审查 Agent", 92, 98),
]

PHASE_RUNNERS = {
    "planning": ("任务规划 Agent", 10, 18, lambda task, output_dir, clients, demo_mode: planning_agent.run(task, output_dir, clients, demo_mode)),
    "collecting": ("信息采集 Agent", 24, 38, lambda task, output_dir, clients, demo_mode: collecting_agent.run(output_dir, clients, demo_mode)),
    "structuring": ("结构化处理 Agent", 44, 58, lambda task, output_dir, clients, demo_mode: structuring_agent.run(output_dir, clients, demo_mode)),
    "comparing": ("对比分析 Agent", 64, 74, lambda task, output_dir, clients, demo_mode: comparing_agent.run(output_dir, clients, demo_mode)),
    "writing": ("报告撰写 Agent", 80, 88, lambda task, output_dir, clients, demo_mode: writing_agent.run(output_dir, clients, demo_mode)),
    "quality": ("质检审查 Agent", 92, 98, lambda task, output_dir, clients, demo_mode: quality_agent.run(output_dir, clients, demo_mode)),
}

ROLLBACK_CHAINS = {
    "collecting": ["collecting", "structuring", "comparing", "writing", "quality"],
    "structuring": ["structuring", "comparing", "writing", "quality"],
    "comparing": ["comparing", "writing", "quality"],
    "writing": ["writing", "quality"],
    "none": [],
    "": [],
}


def should_use_demo(llm: LLMClient, search: SearchClient) -> bool:
    configured = os.getenv("DEMO_MODE", "auto").lower()
    if configured in {"1", "true", "yes"}:
        return True
    if configured in {"0", "false", "no"}:
        return False
    return llm.demo_mode or search.demo_mode


def start_run(task: dict[str, Any], run_id: str | None = None) -> tuple[str, bool]:
    llm = LLMClient()
    search = SearchClient()
    demo_mode = should_use_demo(llm, search)
    run_id = run_id or new_run_id()
    manager = RunManager(run_id, demo_mode=demo_mode)
    manager.write_status("waiting", "", "waiting", 0, "多 Agent 协作流程已创建")
    manager.log("orchestrator", "created", "run_id 已生成")
    return run_id, demo_mode


def run_pipeline(task: dict[str, Any], run_id: str, demo_mode: bool | None = None) -> None:
    llm = LLMClient()
    search = SearchClient()
    fetch = FetchClient()
    if demo_mode is None:
        demo_mode = should_use_demo(llm, search)
    clients = {"llm": llm, "search": search, "fetch": fetch}
    manager = RunManager(run_id, demo_mode=demo_mode)
    output_dir = manager.paths.output_dir

    try:
        manager.write_status("running", "planning", "任务规划 Agent", 1, "开始运行多 Agent 协作流程")
        quality = {}
        for agent_id in ["planning", "collecting", "structuring", "comparing", "writing", "quality"]:
            result = _run_agent_phase(manager, agent_id, task, output_dir, clients, demo_mode)
            if agent_id == "quality":
                quality = result

        if quality.get("rollback_needed"):
            target = quality.get("rollback_target") or "none"
            manager.log("quality", "rollback_needed", f"建议回退到 {target}")
            manager.write_status(
                "running",
                target,
                "自动修订",
                96,
                f"质检建议回退到 {target}，系统执行一次自动修订",
                {target: "rollback_needed"},
            )
            for agent_id in ROLLBACK_CHAINS.get(target, []):
                result = _run_agent_phase(manager, agent_id, task, output_dir, clients, demo_mode, suffix="自动修订" if agent_id != "quality" else "复核")
                if agent_id == "quality":
                    quality = result

        result = build_result(run_id, output_dir, quality)
        write_json(output_dir / "result.json", result)
        manager.write_status(
            "completed",
            "final",
            "最终报告",
            100,
            "多 Agent 协作流程已完成，最终报告已生成",
            {"quality": "completed"},
        )
        manager.log("orchestrator", "completed", "最终报告已生成")
    except Exception as exc:
        manager.write_error("orchestrator", exc)
        manager.write_status("failed", "", "failed", 100, f"运行失败：{exc}")
        manager.log("orchestrator", "failed", str(exc), level="error")


def _run_phase(manager: RunManager, agent_id: str, phase_name: str, start_progress: int, end_progress: int, fn):
    manager.write_status(
        "running",
        agent_id,
        phase_name,
        start_progress,
        f"正在执行：{phase_name}",
        {agent_id: "running"},
    )
    manager.log(agent_id, "started", phase_name)
    result = fn()
    manager.write_status(
        "running",
        agent_id,
        phase_name,
        end_progress,
        f"{phase_name} 已完成",
        {agent_id: "completed"},
    )
    manager.log(agent_id, "completed", phase_name)
    return result


def _run_agent_phase(manager: RunManager, agent_id: str, task: dict[str, Any], output_dir: Path, clients: dict[str, Any], demo_mode: bool, suffix: str = ""):
    phase_name, start_progress, end_progress, runner = PHASE_RUNNERS[agent_id]
    display_name = f"{phase_name} {suffix}".strip()
    return _run_phase(
        manager,
        agent_id,
        display_name,
        start_progress,
        end_progress,
        lambda: runner(task, output_dir, clients, demo_mode),
    )


def build_result(run_id: str, output_dir: Path, quality: dict[str, Any]) -> dict[str, Any]:
    final_report_path = output_dir / "competitive_report_final.md"
    final_report = final_report_path.read_text(encoding="utf-8") if final_report_path.exists() else ""
    return {
        "run_id": run_id,
        "status": "completed",
        "final_report_markdown": final_report,
        "quality_report": quality,
        "planning_result": read_json(output_dir / "planning_result.json", {}),
        "collected_sources": read_json(output_dir / "collected_sources.json", {}),
        "structured_schema_table": read_json(output_dir / "structured_schema_table.json", {}),
        "comparison_analysis": read_json(output_dir / "comparison_analysis.json", {}),
        "report_metadata": read_json(output_dir / "report_metadata.json", {}),
    }


if __name__ == "__main__":
    demo_task = {
        "industry": "AI 会议协作工具赛道",
        "target_companies": ["飞书妙记", "腾讯文档智能助手", "钉钉智能会议", "Notion AI"],
        "dimensions": ["产品定位", "核心功能", "AI能力", "价格模式", "用户反馈", "商业模式"],
        "report_usage": "产品功能规划",
        "source_scope": ["官网", "产品页", "价格页", "帮助文档", "更新日志", "媒体报道", "应用商店评论", "社交平台公开讨论"],
    }
    created_run_id, created_demo_mode = start_run(demo_task)
    run_pipeline(demo_task, created_run_id, created_demo_mode)
    print(created_run_id)
