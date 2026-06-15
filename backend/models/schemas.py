from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


AgentId = Literal["planning", "collecting", "structuring", "comparing", "writing", "quality"]
RunStatus = Literal["waiting", "running", "completed", "failed"]
AgentStatus = Literal["waiting", "running", "completed", "failed", "rollback_needed"]


class RunRequest(BaseModel):
    industry: str = Field(..., min_length=1, max_length=120)
    target_companies: list[str] = Field(..., min_length=1, max_length=6)
    dimensions: list[str] = Field(default_factory=list, max_length=10)
    report_usage: str = Field(default="", max_length=200)
    source_scope: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("target_companies", "dimensions", "source_scope")
    @classmethod
    def strip_items(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        return list(dict.fromkeys(cleaned))


class RunStartResponse(BaseModel):
    run_id: str
    status: Literal["started"]
    message: str
    demo_mode: bool


class StatusResponse(BaseModel):
    run_id: str
    status: RunStatus
    current_agent: str = ""
    current_phase: str = ""
    progress: int = 0
    agent_status: dict[str, AgentStatus]
    latest_log: str = ""
    demo_mode: bool = False
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class LogEntry(BaseModel):
    timestamp: str
    agent: str
    action: str
    detail: str = ""
    level: str = "info"


class AgentArtifactResponse(BaseModel):
    run_id: str
    agent_id: AgentId
    status: str
    content_type: Literal["json", "markdown"]
    data: Any
    demo_mode: bool = False


class FeedbackRequest(BaseModel):
    agent_id: AgentId
    feedback_type: str = Field(..., min_length=1, max_length=80)
    message: str = Field(..., min_length=1, max_length=1000)
    rerun_from: str = Field(default="current", max_length=40)


class FeedbackResponse(BaseModel):
    run_id: str
    status: Literal["received"]
    message: str
