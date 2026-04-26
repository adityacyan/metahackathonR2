"""
LLM-assisted ticket grading for the MigrationEnvironment.

This is optional and designed to be a drop-in replacement for the deterministic
TicketSatisfactionGrader when you want more semantic evaluation (e.g., did the
agent *actually* provide a good v2 alternative, deprecation messaging, etc.).

The implementation uses an OpenAI-compatible Chat Completions API (e.g. the
Hugging Face router at https://router.huggingface.co/v1) via plain `requests`
to avoid adding extra dependencies.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

try:
    from ..migration_models import MigrationTicket
except ImportError:
    from migration_models import MigrationTicket


@dataclass
class LLMTicketGrade:
    score: float
    rationale: str = ""


class LLMTicketSatisfactionGrader:
    """LLM-assisted ticket satisfaction grader with rule-based fallback."""

    def __init__(
        self,
        *,
        api_base_url: str = "https://router.huggingface.co/v1",
        model_name: str = "Qwen/Qwen2.5-Coder-3B-Instruct",
        api_key: Optional[str] = None,
        timeout_s: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key or os.getenv("HF_TOKEN") or os.getenv("API_KEY")
        self.timeout_s = float(timeout_s)
        self.max_retries = int(max_retries)

        if not self.api_key:
            raise ValueError(
                "LLM ticket grading enabled but no API key found. "
                "Set HF_TOKEN (recommended) or API_KEY."
            )

    def score_ticket_satisfaction(
        self,
        *,
        baseline_schema: Dict[str, Any],
        current_schema: Dict[str, Any],
        ticket: MigrationTicket,
    ) -> LLMTicketGrade:
        """Return a score in [0, 1] for ticket satisfaction."""

        # Keep context small-ish; the LLM does not need full OpenAPI for grading.
        baseline_summary = self._schema_summary(baseline_schema)
        current_summary = self._schema_summary(current_schema)

        prompt = self._build_prompt(
            baseline_summary=baseline_summary,
            current_summary=current_summary,
            ticket=ticket,
        )

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                raw = self._call_llm(prompt)
                grade = self._parse_grade(raw)
                return grade
            except Exception as e:
                last_err = e
                # exponential-ish backoff
                time.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"LLM ticket grading failed: {last_err}")

    def _call_llm(self, prompt: str) -> str:
        url = f"{self.api_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are grading an API migration ticket. "
                        "Return ONLY valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 300,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return (content or "").strip()

    def _build_prompt(
        self,
        *,
        baseline_summary: str,
        current_summary: str,
        ticket: MigrationTicket,
    ) -> str:
        ac = "\n".join([f"- {x}" for x in ticket.acceptance_criteria])
        return (
            "GRADE THIS MIGRATION TICKET.\n\n"
            "You must check the CURRENT API against the ticket acceptance criteria.\n"
            "The baseline must remain backward-compatible.\n\n"
            f"BASELINE_API_SUMMARY:\n{baseline_summary}\n\n"
            f"CURRENT_API_SUMMARY:\n{current_summary}\n\n"
            "TICKET:\n"
            f"id: {ticket.ticket_id}\n"
            f"type: {ticket.ticket_type}\n"
            f"title: {ticket.title}\n"
            f"acceptance_criteria:\n{ac}\n\n"
            "Return JSON exactly in this format:\n"
            "{\n"
            '  "score": 0.0,\n'
            '  "rationale": "short reason"\n'
            "}\n"
            "Rules:\n"
            "- score is a float in [0, 1]\n"
            "- score=1 means all acceptance criteria are clearly satisfied\n"
            "- score=0 means none are satisfied\n"
        )

    def _parse_grade(self, text: str) -> LLMTicketGrade:
        payload = text.strip()
        # strip ```json fences if present
        if payload.startswith("```"):
            lines = payload.splitlines()
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            payload = "\n".join(json_lines).strip()

        obj = json.loads(payload)
        score = float(obj.get("score", 0.0))
        score = max(0.0, min(1.0, score))
        rationale = str(obj.get("rationale", "") or "")
        return LLMTicketGrade(score=score, rationale=rationale)

    def _schema_summary(self, schema: Dict[str, Any]) -> str:
        if not isinstance(schema, dict):
            return ""
        lines = []
        info = schema.get("info", {}) if isinstance(schema.get("info", {}), dict) else {}
        lines.append(f"openapi: {schema.get('openapi', '')}")
        lines.append(f"info: title={info.get('title','')} version={info.get('version','')}")
        paths = schema.get("paths", {})
        if isinstance(paths, dict):
            for path, item in list(paths.items())[:25]:
                if not isinstance(item, dict):
                    continue
                for method in ["get", "post", "put", "patch", "delete"]:
                    if method in item and isinstance(item.get(method), dict):
                        op = item[method]
                        dep = " deprecated=true" if op.get("deprecated") else ""
                        lines.append(f"{method.upper()} {path}{dep}")
        return "\n".join(lines)

