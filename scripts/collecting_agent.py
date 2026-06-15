from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common import copy_demo, credibility_for, now, read_json, source_type_for, write_json


def run(output_dir: Path, clients: dict[str, Any], demo_mode: bool) -> dict[str, Any]:
    if demo_mode:
        copy_demo("collected_sources.json", output_dir)
        return read_json(output_dir / "collected_sources.json", {})

    planning = read_json(output_dir / "planning_result.json", {})
    search_client = clients["search"]
    fetch_client = clients["fetch"]
    competitors = []
    for name in planning.get("competitor_scope", []):
        packets = []
        queries = [
            f"{name} {planning.get('analysis_goal', '')} 产品 功能",
            f"{name} 定价 价格 帮助文档 更新日志",
            f"{name} 用户 评论 体验 媒体报道",
        ]
        for query in queries:
            try:
                results = search_client.search(query, max_results=3)
            except Exception:
                results = []
            for item in results:
                fetched = fetch_client.fetch(item.get("url", ""), item.get("title", ""), item.get("snippet", ""))
                source_type = source_type_for(f"{fetched['url']} {fetched['title']} {query}")
                packets.append(
                    {
                        "title": fetched["title"],
                        "url": fetched["url"],
                        "source_type": source_type,
                        "retrieved_at": fetched["retrieved_at"],
                        "excerpt": (fetched["content"] or fetched["snippet"])[:500],
                        "credibility": credibility_for(source_type),
                        "fields_supported": _fields_supported(source_type),
                    }
                )
        if not packets:
            packets.append(
                {
                    "title": f"{name} 公开资料不足",
                    "url": "",
                    "source_type": "other",
                    "retrieved_at": now(),
                    "excerpt": "未获取到足够公开资料",
                    "credibility": "low",
                    "fields_supported": [],
                }
            )
        competitors.append(
            {
                "name": name,
                "source_packets": packets[:8],
                "missing_information": _missing_information(packets),
                "source_coverage_score": min(100, len({p["source_type"] for p in packets}) * 16),
            }
        )
    result = {
        "agent": "collecting",
        "status": "completed",
        "competitors": competitors,
        "retrieved_at": now(),
        "handoff_to_next_agent": {
            "next_agent": "structuring",
            "materials": ["公开资料包", "来源清单", "资料摘录", "信息缺口", "来源可信度标记"],
        },
    }
    write_json(output_dir / "collected_sources.json", result)
    return result


def _fields_supported(source_type: str) -> list[str]:
    mapping = {
        "official_site": ["product_positioning", "core_features"],
        "docs": ["use_cases", "ai_capabilities"],
        "pricing": ["pricing_model", "business_model"],
        "news": ["recent_updates", "strengths"],
        "app_store": ["user_feedback", "weaknesses"],
        "social": ["user_feedback"],
    }
    return mapping.get(source_type, ["product_positioning"])


def _missing_information(packets: list[dict[str, Any]]) -> list[str]:
    if len(packets) == 1 and packets[0].get("excerpt") == "未获取到足够公开资料":
        return ["价格模式", "用户反馈", "帮助文档", "近期动态"]
    source_types = {packet["source_type"] for packet in packets}
    missing = []
    if "pricing" not in source_types:
        missing.append("价格模式")
    if not ({"app_store", "social"} & source_types):
        missing.append("用户反馈")
    if "docs" not in source_types:
        missing.append("使用场景和帮助文档")
    return missing
