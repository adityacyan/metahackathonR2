#!/usr/bin/env python3
"""
Inference Script for API Lifecycle Migration Environment.

MANDATORY Environment Variables:
- API_BASE_URL: LLM endpoint (default: HuggingFace router)
- MODEL_NAME: Model identifier
- HF_TOKEN or API_KEY: API key
- ENV_SERVER_URL: Environment server URL (default: http://localhost:7860)

STDOUT FORMAT:
- [START] task=<task> env=<env> model=<model>
- [STEP] step=<n> action=<json> reward=<0.00> done=<true|false> error=<msg|null>
- [END] success=<true|false> steps=<n> score=<0.000> rewards=<r1,r2,...>
"""

import asyncio
import json
import math
import os
import sys
import textwrap
from datetime import datetime
from typing import List, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from openenv.core import EnvClient
    from migration_models import MigrationAction, MigrationObservation
except ImportError:
    from api_conformance_gym.migration_models import MigrationAction, MigrationObservation

# Configuration
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-Coder-3B-Instruct:nscale")
ENV_SERVER_URL = os.getenv("ENV_SERVER_URL", "http://localhost:7860")
TASK_NAME = "api-lifecycle-migration"
BENCHMARK = "api_lifecycle_migration"
MAX_STEPS = 15
TEMPERATURE = 0.3
MAX_TOKENS = 10000
SUCCESS_SCORE_THRESHOLD = 0.5
BASELINE_EPISODES = 3
LOG_FILE_PATH = os.path.join(current_dir, "log.txt")

if not API_KEY:
    print("[ERROR] No API key found. Set HF_TOKEN, API_KEY, or OPENAI_API_KEY.", flush=True)
    sys.exit(1)


def _strict_score(value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.01
    if not math.isfinite(v):
        v = 0.01
    v = max(0.01, min(0.99, v))
    return float(f"{v:.2f}")


def _single_line(text: str) -> str:
    return " ".join(str(text).split())


SYSTEM_PROMPT = textwrap.dedent("""
You are an expert API platform engineer. Your job is to iteratively evolve an OpenAPI 3.0/3.1 schema while maintaining backward compatibility for existing clients.

Hard constraints:
- Output MUST be valid JSON only (no markdown, no commentary).
- Output MUST be a complete OpenAPI schema object.
- NEVER remove existing endpoints, operations, or response fields used by clients.
- Prefer additive changes (new endpoints, new optional fields) over breaking changes.
- Keep v1 stable. If a breaking change is required, introduce v2 endpoints while keeping v1 working.
- Every operation must be protected by a security scheme (global or per-operation).
- Use `deprecated: true` when asked to deprecate; deprecated endpoints must remain functional.
- Provide summaries/descriptions for all operations.

You will receive:
1. Baseline schema (the v1 schema you must evolve)
2. Active migration ticket with acceptance criteria
3. Contract test report (what clients require and what broke)
4. Validator feedback

Goal: maximize contract pass rate + satisfy tickets with minimal breaking changes.

Return ONLY the updated OpenAPI schema JSON.
""").strip()


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    reward_val = _strict_score(reward)
    error_val = _single_line(error) if error else "null"
    action_preview = _single_line(action)
    action_preview = action_preview[:100] + "..." if len(action_preview) > 100 else action_preview
    print(f"[STEP] step={step} action={action_preview} reward={reward_val:.2f} done={str(done).lower()} error={error_val}", flush=True)


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    safe_score = _strict_score(score)
    rewards_str = ",".join(f"{_strict_score(r):.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={safe_score:.2f} rewards={rewards_str}", flush=True)


def build_user_prompt(obs: "MigrationObservation", step: int) -> str:
    ticket = obs.active_ticket
    ticket_text = "No active ticket."
    if ticket:
        criteria = "\n".join(f"  - {c}" for c in ticket.acceptance_criteria)
        ticket_text = f"[{ticket.ticket_type.upper()}] {ticket.title}\n{ticket.description}\nAcceptance criteria:\n{criteria}"

    contract = obs.contract_test_report
    contract_text = f"Pass rate: {contract.contract_pass_rate:.1%}"
    if contract.contract_failures:
        contract_text += "\nFailures:\n" + "\n".join(f"  - {f}" for f in contract.contract_failures[:5])

    breaking = obs.breaking_change_report
    breaking_text = f"Breaking changes: {breaking.breaking_change_count}"
    if breaking.breaking_changes:
        breaking_text += "\n" + "\n".join(f"  - {c}" for c in breaking.breaking_changes[:3])

    return textwrap.dedent(f"""
BASELINE_SCHEMA_JSON:
{obs.baseline_schema_json}

ACTIVE_TICKET (step {step}):
{ticket_text}

CONTRACT_TEST_REPORT:
{contract_text}

BREAKING_CHANGES:
{breaking_text}

VALIDATION_FEEDBACK:
- validity_score: {obs.validity_score:.2f}
- best_practices_score: {obs.best_practices_score:.2f}
- ticket_satisfaction: {obs.ticket_satisfaction_score:.2f}
- tickets_completed: {obs.tickets_completed}/{obs.total_tickets}
- feedback: {obs.schema_feedback}

Return ONLY valid JSON.
""").strip()


def get_model_response(client: OpenAI, obs: "MigrationObservation", step: int) -> Tuple[str, str]:
    user_prompt = build_user_prompt(obs, step)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        response = (completion.choices[0].message.content or "").strip()
        if response.startswith("```"):
            lines = response.split("\n")
            json_lines, in_block = [], False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            response = "\n".join(json_lines)
        json.loads(response)
        return response, "llm"
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)

    # Fallback: return baseline schema unchanged
    return obs.baseline_schema_json, "fallback"


async def run_episode(env, client: OpenAI, episode_index: int) -> dict:
    rewards: List[float] = []
    steps_taken = 0
    score = 0.01

    try:
        result = await env.reset()
        obs = result.observation
        log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

        for step in range(1, MAX_STEPS + 1):
            schema_json, source = await asyncio.to_thread(get_model_response, client, obs, step)
            action = MigrationAction(schema_json=schema_json, iteration=step)
            result = await env.step(action)
            obs = result.observation
            reward = _strict_score(result.reward if result.reward is not None else 0.01)
            done = result.done
            error = getattr(result, "last_action_error", None)

            rewards.append(reward)
            steps_taken = step
            log_step(step=step, action=schema_json, reward=reward, done=done, error=error)

            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                ts = datetime.utcnow().isoformat() + "Z"
                f.write(f"\n[{ts}] episode={episode_index} step={step} source={source} reward={reward:.3f} done={str(done).lower()}\n")

            if done:
                break

        executed = max(steps_taken, 1)
        score = _strict_score(sum(rewards) / executed)
        return {"steps": steps_taken, "score": score, "success": score >= SUCCESS_SCORE_THRESHOLD, "rewards": rewards}

    except Exception as e:
        print(f"[DEBUG] Episode {episode_index} error: {e}", flush=True)
        return {"steps": steps_taken, "score": score, "success": False, "rewards": rewards}


async def main() -> None:
    from openenv.core import EnvClient
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    print(f"[INFO] Connecting to {ENV_SERVER_URL}", flush=True)

    # Import the migration client
    try:
        from client import MigrationEnvClient
        env = MigrationEnvClient(base_url=ENV_SERVER_URL)
    except ImportError:
        from openenv.core import EnvClient
        env = EnvClient(base_url=ENV_SERVER_URL)

    with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.utcnow().isoformat()}Z] run_start env={BENCHMARK} model={MODEL_NAME} episodes={BASELINE_EPISODES}\n")

    episode_results = []
    try:
        for i in range(1, BASELINE_EPISODES + 1):
            try:
                ep = await run_episode(env, client, i)
            except Exception as exc:
                print(f"[DEBUG] Episode {i} failed: {exc}", flush=True)
                ep = {"steps": 0, "score": 0.01, "success": False, "rewards": []}
            episode_results.append(ep)
            log_end(success=ep["success"], steps=ep["steps"], score=ep["score"], rewards=ep["rewards"])

        agg = _strict_score(sum(e["score"] for e in episode_results) / len(episode_results))
        passed = sum(1 for e in episode_results if e["success"])
        print(f"[BASELINE] episodes={len(episode_results)} passed={passed} aggregate_score={agg:.2f}", flush=True)
    finally:
        try:
            await env.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
