from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "output"
LOGS_ROOT = ROOT / "logs"
DEMO_ROOT = ROOT / "data" / "demo"

AGENTS = ["planning", "collecting", "structuring", "comparing", "writing", "quality"]


def utc_now() -> str:
    return datetime.utcnow().isoformat()


def new_run_id() -> str:
    return f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


class RunPaths:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.output_dir = OUTPUT_ROOT / run_id
        self.log_dir = LOGS_ROOT / run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def status_file(self) -> Path:
        return self.log_dir / "status.json"

    @property
    def pipeline_file(self) -> Path:
        return self.log_dir / "pipeline.json"

    @property
    def error_file(self) -> Path:
        return self.log_dir / "error.json"


class RunManager:
    def __init__(self, run_id: str, demo_mode: bool = False) -> None:
        self.paths = RunPaths(run_id)
        self.demo_mode = demo_mode
        if not self.paths.pipeline_file.exists():
            self.write_json(self.paths.pipeline_file, [])
        if not self.paths.status_file.exists():
            self.write_status("waiting", "", "", 0, "等待启动多 Agent 协作流程")

    def write_status(
        self,
        status: str,
        current_agent: str,
        current_phase: str,
        progress: int,
        latest_log: str,
        agent_status: dict[str, str] | None = None,
    ) -> None:
        existing = self.read_json(self.paths.status_file, default={})
        current_agent_status = existing.get("agent_status") or {agent: "waiting" for agent in AGENTS}
        if agent_status:
            current_agent_status.update(agent_status)
        payload = {
            "run_id": self.paths.run_id,
            "status": status,
            "current_agent": current_agent,
            "current_phase": current_phase,
            "progress": progress,
            "agent_status": current_agent_status,
            "latest_log": latest_log,
            "demo_mode": self.demo_mode,
            "updated_at": utc_now(),
        }
        self.write_json(self.paths.status_file, payload)

    def log(self, agent: str, action: str, detail: str = "", level: str = "info") -> None:
        entry = {
            "timestamp": utc_now(),
            "agent": agent,
            "action": action,
            "detail": detail,
            "level": level,
        }
        logs = self.read_json(self.paths.pipeline_file, default=[])
        logs.append(entry)
        self.write_json(self.paths.pipeline_file, logs)

    def write_error(self, agent: str, error: Exception) -> None:
        self.write_json(
            self.paths.error_file,
            {
                "run_id": self.paths.run_id,
                "agent": agent,
                "error": str(error),
                "updated_at": utc_now(),
            },
        )

    @staticmethod
    def read_json(path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)


def safe_child(root: Path, *parts: str) -> Path:
    root_resolved = root.resolve()
    target = root.joinpath(*parts).resolve()
    if root_resolved != target and root_resolved not in target.parents:
        raise ValueError("Unsafe path access blocked")
    return target
