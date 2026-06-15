from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


class LLMClient:
    """Small OpenAI-compatible client used by every Agent.

    If no API key is configured, `demo_mode` is true and callers should use
    deterministic local mock data instead of attempting a network request.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.demo_mode = not bool(self.api_key)

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        if self.demo_mode:
            return ""
        payload = self._payload(prompt, system_prompt)
        data = self._post("/chat/completions", payload)
        return data["choices"][0]["message"]["content"]

    def generate_json(self, prompt: str, schema: dict[str, Any], system_prompt: str | None = None) -> dict[str, Any]:
        if self.demo_mode:
            return {}
        json_prompt = (
            f"{prompt}\n\n请只输出合法 JSON，不要使用 Markdown 代码块。"
            f"\n目标 JSON Schema 描述：\n{json.dumps(schema, ensure_ascii=False)}"
        )
        text = self.generate_text(json_prompt, system_prompt)
        parsed = self._parse_json(text)
        if parsed is None:
            self.last_warning = "LLM returned non-JSON content; falling back to local logic."
            return {}
        return parsed

    def _payload(self, prompt: str, system_prompt: str | None) -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return {"model": self.model, "messages": messages, "temperature": 0.2}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM API failed: {exc.code} {body[:500]}") from exc

    @classmethod
    def _parse_json(cls, text: str) -> dict[str, Any] | None:
        cleaned = text.strip()
        candidates = [cleaned]

        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.I)
        if fence_match:
            candidates.append(fence_match.group(1).strip())

        object_candidate = cls._extract_balanced(cleaned, "{", "}")
        if object_candidate:
            candidates.append(object_candidate)

        array_candidate = cls._extract_balanced(cleaned, "[", "]")
        if array_candidate:
            candidates.append(array_candidate)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list):
                    return {"items": parsed}
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _extract_balanced(text: str, open_char: str, close_char: str) -> str:
        start = text.find(open_char)
        if start == -1:
            return ""
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        return ""
