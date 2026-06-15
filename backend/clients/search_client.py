from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class SearchClient:
    """Tavily-backed search client with automatic demo-mode fallback."""

    def __init__(self) -> None:
        self.api_key = os.getenv("TAVILY_API_KEY", "").strip()
        self.demo_mode = not bool(self.api_key)
        self.warnings: list[str] = []

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if self.demo_mode:
            return []
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max(1, min(max_results, 10)),
            "include_answer": False,
            "include_raw_content": False,
        }
        request = urllib.request.Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "score": item.get("score", 0),
                }
                for item in data.get("results", [])
            ]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            self.warnings.append(f"Search failed for query: {query}. Reason: {exc}")
            return []
