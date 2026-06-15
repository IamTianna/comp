from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.run_manager import DEMO_ROOT


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def copy_demo(filename: str, output_dir: Path) -> Path:
    source = DEMO_ROOT / filename
    target = output_dir / filename
    shutil.copyfile(source, target)
    return target


def now() -> str:
    return datetime.utcnow().isoformat()


def markdown_from_sources(title: str, sections: list[tuple[str, str]]) -> str:
    body = [f"# {title}", ""]
    for section_title, content in sections:
        body.extend([f"## {section_title}", "", content.strip(), ""])
    return "\n".join(body).strip() + "\n"


def source_type_for(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ["price", "pricing", "价格"]):
        return "pricing"
    if any(word in lower for word in ["docs", "help", "文档", "帮助"]):
        return "docs"
    if any(word in lower for word in ["news", "媒体", "报道"]):
        return "news"
    if any(word in lower for word in ["app", "store", "评论"]):
        return "app_store"
    if any(word in lower for word in ["twitter", "x.com", "weibo", "知乎", "social"]):
        return "social"
    if any(word in lower for word in ["official", "官网", ".com"]):
        return "official_site"
    return "other"


def credibility_for(source_type: str) -> str:
    if source_type in {"official_site", "docs", "pricing"}:
        return "high"
    if source_type in {"news", "app_store"}:
        return "medium"
    return "low"
