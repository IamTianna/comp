from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from datetime import datetime


class FetchClient:
    def __init__(self) -> None:
        self.timeout = int(os.getenv("FETCH_TIMEOUT_SECONDS", "12"))

    def fetch(self, url: str, fallback_title: str = "", fallback_snippet: str = "") -> dict[str, str]:
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; CompetitiveAgent/1.0)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(800_000).decode("utf-8", errors="ignore")
            title = self._extract_title(raw) or fallback_title
            content = self._clean_html(raw)
            return {
                "title": title,
                "url": url,
                "snippet": fallback_snippet,
                "content": content[:8000],
                "retrieved_at": datetime.utcnow().isoformat(),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return {
                "title": fallback_title,
                "url": url,
                "snippet": fallback_snippet,
                "content": fallback_snippet,
                "retrieved_at": datetime.utcnow().isoformat(),
            }

    @staticmethod
    def _extract_title(html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""

    @staticmethod
    def _clean_html(html: str) -> str:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;|&#160;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
