from __future__ import annotations

import sys
from pathlib import Path
from threading import Thread
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models.schemas import AgentArtifactResponse, FeedbackRequest, FeedbackResponse, RunRequest, RunStartResponse
from backend.services import artifact_loader
from backend.services.run_manager import LOGS_ROOT, RunManager, safe_child, utc_now
from scripts.orchestrator import run_pipeline, start_run


app = FastAPI(title="Competitive Analysis Agent Collaboration System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/runs", response_model=RunStartResponse)
def create_run(request: RunRequest, background_tasks: BackgroundTasks) -> RunStartResponse:
    task = request.model_dump()
    run_id, demo_mode = start_run(task)
    background_tasks.add_task(_run_in_thread, task, run_id, demo_mode)
    return RunStartResponse(
        run_id=run_id,
        status="started",
        message="多 Agent 协作流程已启动",
        demo_mode=demo_mode,
    )


@app.get("/api/runs/{run_id}/status")
def get_status(run_id: str) -> dict[str, Any]:
    status = artifact_loader.load_status(run_id)
    if not status:
        raise HTTPException(status_code=404, detail="run_id not found")
    return status


@app.get("/api/runs/{run_id}/logs")
def get_logs(run_id: str) -> dict[str, Any]:
    return {"logs": artifact_loader.load_logs(run_id)}


@app.get("/api/runs/{run_id}/agent/{agent_id}", response_model=AgentArtifactResponse)
def get_agent(run_id: str, agent_id: str) -> AgentArtifactResponse:
    try:
        content_type, data = artifact_loader.load_agent_artifact(run_id, agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    status = artifact_loader.load_status(run_id)
    return AgentArtifactResponse(
        run_id=run_id,
        agent_id=agent_id,
        status=status.get("agent_status", {}).get(agent_id, "waiting"),
        content_type=content_type,
        data=data,
        demo_mode=status.get("demo_mode", False),
    )


@app.get("/api/runs/{run_id}/result")
def get_result(run_id: str) -> dict[str, Any]:
    result = artifact_loader.load_result(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="result not found")
    return result


@app.get("/api/runs/{run_id}/artifacts")
def get_artifacts(run_id: str) -> dict[str, Any]:
    return artifact_loader.list_artifacts(run_id)


@app.post("/api/runs/{run_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(run_id: str, request: FeedbackRequest) -> FeedbackResponse:
    status_path = safe_child(LOGS_ROOT, run_id, "status.json")
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="run_id not found")
    feedback_path = safe_child(LOGS_ROOT, run_id, "feedback.json")
    feedback = RunManager.read_json(feedback_path, default=[])
    feedback.append(
        {
            "timestamp": utc_now(),
            "agent_id": request.agent_id,
            "feedback_type": request.feedback_type,
            "message": request.message,
            "rerun_from": request.rerun_from,
        }
    )
    RunManager.write_json(feedback_path, feedback)
    return FeedbackResponse(run_id=run_id, status="received", message="修改意见已记录")


def _run_in_thread(task: dict[str, Any], run_id: str, demo_mode: bool) -> None:
    # Keep BackgroundTasks responsive even when a real search/LLM call is slow.
    thread = Thread(target=run_pipeline, args=(task, run_id, demo_mode), daemon=True)
    thread.start()
