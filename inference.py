#!/usr/bin/env python3
"""Baseline inference script for API Lifecycle Migration environment."""

import asyncio
import inspect
import json
import math
import os
import re
import sys
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from migration_models import MigrationAction, MigrationObservation
from training.reliability import (
    strict_extract_json_object,
    repair_extract_json_object,
    canonicalize_json_object,
)

try:
    from client import MigrationEnvClient
except ImportError:
    MigrationEnvClient = None

from openenv.core import EnvClient

# Configuration
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-Coder-3B-Instruct")
ENV_SERVER_URL = os.getenv("ENV_SERVER_URL", "http://localhost:7860")

TASK_NAME = "api-lifecycle-migration"
BENCHMARK = "api_lifecycle_migration"
MAX_STEPS = int(os.getenv("MAX_STEPS", "15"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4000"))
SUCCESS_SCORE_THRESHOLD = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.5"))
BASELINE_EPISODES = int(os.getenv("BASELINE_EPISODES", "3"))
LOG_FILE_PATH = os.path.join(current_dir, "log.txt")

SYSTEM_PROMPT = textwrap.dedent(
    """
You are an expert API platform engineer. Evolve an OpenAPI schema while preserving backward compatibility.

Hard constraints:
- Output valid JSON only (no markdown).
- Keep existing v1 operations and fields functional.
- Prefer additive changes over breaking changes.
- Keep security protection on all operations.
- For deprecation tasks, use deprecated: true while keeping behavior intact.

Return only the full updated OpenAPI schema JSON object.
"""
).strip()


def _safe_score(value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    if not math.isfinite(v):
        v = 0.0
    return max(0.0, min(1.0, v))


def _single_line(text: Any) -> str:
    return " ".join(str(text).split())


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return {}


def _extract_json_content(text: str) -> str:
    payload = (text or "").strip()
    if not payload.startswith("```"):
        return payload

    lines = payload.splitlines()
    json_lines: List[str] = []
    in_block = False
    for line in lines:
        if line.strip().startswith("```"):
            in_block = not in_block
            continue
        if in_block:
            json_lines.append(line)
    return "\n".join(json_lines).strip()


def _normalize_json_output_strict(text: str) -> Optional[str]:
    """Strict parse path for production success metric."""
    diag = strict_extract_json_object((text or "").strip())
    if not diag.strict_ok or not isinstance(diag.parsed_obj, dict):
        return None
    return canonicalize_json_object(diag.parsed_obj)


def _normalize_json_output_repair(text: str) -> Optional[str]:
    """Permissive fallback parser (used only after strict parse fails)."""
    payload = _extract_json_content(text)
    obj = repair_extract_json_object(payload)
    if not isinstance(obj, dict):
        return None
    return canonicalize_json_object(obj)


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
    reward_val = _safe_score(reward)
    error_val = _single_line(error) if error else "null"
    action_preview = _single_line(action)
    if len(action_preview) > 100:
        action_preview = action_preview[:100] + "..."
    print(
        f"[STEP] step={step} action={action_preview} reward={reward_val:.3f} done={str(done).lower()} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    safe_score = _safe_score(score)
    rewards_str = ",".join(f"{_safe_score(r):.3f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={safe_score:.3f} rewards={rewards_str}",
        flush=True,
    )


def build_user_prompt(obs: "MigrationObservation", step: int) -> str:
    ticket = getattr(obs, "active_ticket", None)
    ticket_text = "No active ticket."
    if ticket:
        criteria_list = getattr(ticket, "acceptance_criteria", []) or []
        criteria = "\n".join(f"  - {c}" for c in criteria_list)
        ticket_text = (
            f"[{getattr(ticket, 'ticket_type', 'unknown').upper()}] "
            f"{getattr(ticket, 'title', 'Untitled')}\n"
            f"{getattr(ticket, 'description', '')}\n"
            f"Acceptance criteria:\n{criteria}"
        )

    contract = getattr(obs, "contract_test_report", None)
    contract_pass_rate = _safe_score(getattr(contract, "contract_pass_rate", 0.0))
    contract_failures = getattr(contract, "contract_failures", []) if contract else []
    contract_text = f"Pass rate: {contract_pass_rate:.1%}"
    if contract_failures:
        contract_text += "\nFailures:\n" + "\n".join(
            f"  - {f}" for f in contract_failures[:5]
        )

    breaking = getattr(obs, "breaking_change_report", None)
    breaking_count = getattr(breaking, "breaking_change_count", 0)
    breaking_items = getattr(breaking, "breaking_changes", []) if breaking else []
    breaking_text = f"Breaking changes: {breaking_count}"
    if breaking_items:
        lines: List[str] = []
        for item in breaking_items[:3]:
            if isinstance(item, str):
                lines.append(item)
            else:
                item_dict = _as_dict(item)
                lines.append(item_dict.get("description", str(item)))
        breaking_text += "\n" + "\n".join(f"  - {line}" for line in lines)

    return textwrap.dedent(
        f"""
BASELINE_SCHEMA_JSON:
{obs.baseline_schema_json}

ACTIVE_TICKET (step {step}):
{ticket_text}

CONTRACT_TEST_REPORT:
{contract_text}

BREAKING_CHANGES:
{breaking_text}

VALIDATION_FEEDBACK:
- validity_score: {_safe_score(getattr(obs, 'validity_score', 0.0)):.2f}
- best_practices_score: {_safe_score(getattr(obs, 'best_practices_score', 0.0)):.2f}
- ticket_satisfaction: {_safe_score(getattr(obs, 'ticket_satisfaction_score', 0.0)):.2f}
- tickets_completed: {getattr(obs, 'tickets_completed', 0)}/{getattr(obs, 'total_tickets', 0)}
- feedback: {getattr(obs, 'schema_feedback', '')}

Return ONLY valid JSON.
"""
    ).strip()


def _ensure_security(schema: Dict[str, Any]) -> None:
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    if not security_schemes:
        security_schemes["apiKey"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }

    if "security" not in schema:
        scheme_name = next(iter(security_schemes.keys()))
        schema["security"] = [{scheme_name: []}]


def _ensure_operation_docs(schema: Dict[str, Any]) -> None:
    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(op, dict):
                continue
            op.setdefault("summary", f"{method.upper()} {path}")
            op.setdefault("description", f"{method.upper()} operation for {path}")


def _apply_ticket_heuristics(base_schema_json: str, obs: "MigrationObservation") -> str:
    try:
        schema = json.loads(base_schema_json)
        if not isinstance(schema, dict):
            schema = {}
    except Exception:
        schema = {}

    schema.setdefault("openapi", "3.0.0")
    schema.setdefault("info", {"title": "Migrated API", "version": "1.0.0"})
    schema.setdefault("paths", {})

    _ensure_security(schema)
    _ensure_operation_docs(schema)

    ticket = getattr(obs, "active_ticket", None)
    ticket_type = (getattr(ticket, "ticket_type", "") or "").lower()

    if ticket_type == "additive":
        if "/v1/reviews" not in schema["paths"]:
            schema["paths"]["/v1/reviews"] = {
                "get": {
                    "summary": "List reviews",
                    "description": "List available reviews",
                    "responses": {"200": {"description": "Reviews list"}},
                },
                "post": {
                    "summary": "Create review",
                    "description": "Create a review record",
                    "responses": {"201": {"description": "Review created"}},
                },
            }
    elif ticket_type == "security":
        _ensure_security(schema)
    elif ticket_type == "compliance":
        _ensure_operation_docs(schema)
    elif ticket_type == "deprecation":
        for _, path_item in schema.get("paths", {}).items():
            if isinstance(path_item, dict):
                for _, op in path_item.items():
                    if isinstance(op, dict):
                        op.setdefault("deprecated", True)
                break
        schema["paths"].setdefault(
            "/v2/search",
            {
                "get": {
                    "summary": "Search resources",
                    "description": "Version 2 search endpoint",
                    "responses": {"200": {"description": "Search results"}},
                }
            },
        )

    return json.dumps(schema, separators=(",", ":"))


def get_model_response(
    client: Optional[OpenAI],
    obs: "MigrationObservation",
    step: int,
    current_schema_json: str,
) -> Tuple[str, str]:
    if client is None:
        return _apply_ticket_heuristics(current_schema_json, obs), "heuristic"

    user_prompt = build_user_prompt(obs, step)
    try:
        # Retry once with stricter decoding if the first output is not parseable JSON.
        for attempt in range(2):
            request_kwargs = dict(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=(TEMPERATURE if attempt == 0 else 0.0),
                max_tokens=MAX_TOKENS,
            )
            try:
                # OpenAI-compatible endpoints that support this enforce JSON object output.
                completion = client.chat.completions.create(
                    **request_kwargs, response_format={"type": "json_object"}
                )
            except Exception:
                # Some routers do not support response_format; retry without it.
                completion = client.chat.completions.create(**request_kwargs)
            content = completion.choices[0].message.content or ""
            normalized = _normalize_json_output_strict(content)
            if normalized is not None:
                return normalized, "llm"

            # Repair is allowed only in controlled production fallback.
            repaired = _normalize_json_output_repair(content)
            if repaired is not None:
                return repaired, "llm-repair-fallback"
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return _apply_ticket_heuristics(current_schema_json, obs), "heuristic-fallback"

    return _apply_ticket_heuristics(current_schema_json, obs), "heuristic-fallback"


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _extract_observation(result: Any) -> MigrationObservation:
    if hasattr(result, "observation"):
        return result.observation
    return result


async def run_episode(
    env: Any, client: Optional[OpenAI], episode_index: int
) -> Dict[str, Any]:
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0

    try:
        reset_result = await _maybe_await(env.reset())
        obs = _extract_observation(reset_result)
        current_schema_json = getattr(obs, "baseline_schema_json", "{}")

        log_start(
            task=TASK_NAME, env=BENCHMARK, model=(MODEL_NAME if client else "heuristic")
        )

        for step in range(1, MAX_STEPS + 1):
            schema_json, source = await asyncio.to_thread(
                get_model_response, client, obs, step, current_schema_json
            )
            action = MigrationAction(schema_json=schema_json, iteration=step)
            step_result = await _maybe_await(env.step(action))
            obs = _extract_observation(step_result)

            reward = _safe_score(getattr(step_result, "reward", 0.0))
            done = bool(getattr(step_result, "done", False))
            error = getattr(step_result, "last_action_error", None)

            rewards.append(reward)
            steps_taken = step
            current_schema_json = schema_json

            log_step(
                step=step, action=schema_json, reward=reward, done=done, error=error
            )

            with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
                ts = datetime.utcnow().isoformat() + "Z"
                log_file.write(
                    f"[{ts}] episode={episode_index} step={step} source={source} reward={reward:.3f} done={str(done).lower()}\n"
                )

            if done:
                break

        executed = max(steps_taken, 1)
        score = _safe_score(sum(rewards) / executed)
        return {
            "steps": steps_taken,
            "score": score,
            "success": score >= SUCCESS_SCORE_THRESHOLD,
            "rewards": rewards,
        }
    except Exception as exc:
        print(f"[DEBUG] Episode {episode_index} error: {exc}", flush=True)
        return {
            "steps": steps_taken,
            "score": score,
            "success": False,
            "rewards": rewards,
        }


async def main() -> None:
    print(f"[INFO] Connecting to {ENV_SERVER_URL}", flush=True)

    client: Optional[OpenAI] = None
    if OpenAI is not None and API_KEY:
        client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    else:
        print(
            "[INFO] No API key/OpenAI client found; running in heuristic mode.",
            flush=True,
        )

    if MigrationEnvClient is not None:
        env = MigrationEnvClient(base_url=ENV_SERVER_URL)
    else:
        env = EnvClient(base_url=ENV_SERVER_URL)

    with open(LOG_FILE_PATH, "w", encoding="utf-8") as log_file:
        model_name = MODEL_NAME if client else "heuristic"
        log_file.write(
            f"[{datetime.utcnow().isoformat()}Z] run_start env={BENCHMARK} model={model_name} episodes={BASELINE_EPISODES}\n"
        )

    episode_results: List[Dict[str, Any]] = []
    try:
        for i in range(1, BASELINE_EPISODES + 1):
            ep = await run_episode(env, client, i)
            episode_results.append(ep)
            log_end(
                success=ep["success"],
                steps=ep["steps"],
                score=ep["score"],
                rewards=ep["rewards"],
            )

        agg = _safe_score(
            sum(e["score"] for e in episode_results) / max(len(episode_results), 1)
        )
        passed = sum(1 for e in episode_results if e["success"])
        print(
            f"[BASELINE] episodes={len(episode_results)} passed={passed} aggregate_score={agg:.3f}",
            flush=True,
        )
    finally:
        try:
            await _maybe_await(env.close())
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
