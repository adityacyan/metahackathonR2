# HANDOFF — Round 2 Environment (API Lifecycle v1 → v2 Migration)

## 1) One-line goal
Build an OpenEnv environment where an agent **evolves an existing v1 OpenAPI schema over many steps** while **preserving backward compatibility for existing clients**, and introducing v2 only when breaking changes are needed.

Theme fit: **Theme #2 (Super) Long-Horizon Planning & Instruction Following**  
Real-world fit: API versioning, deprecation, contract stability (platform engineering / governance).

---

## 2) Core environment loop (Reset/Step)

### Reset() must return
- A **baseline v1 schema JSON** (non-empty; already mostly valid)
- A **contract suite** derived from that v1 schema (client expectations)
- Ticket queue (change requests to be applied over time)
- Observation should include at least (can be in `episode_info` dict if easiest):
  - `baseline_schema_json`
  - `active_ticket`
  - `contract_suite_summary` (what’s required)
  - `task_name="API Lifecycle Migration"` (or similar)

### Step(action: schema_json) must do
Given the submitted schema (full OpenAPI JSON):
1. Run existing validators (JSON/OpenAPI/Auth/Best Practices).
2. Run **contract tests** against the baseline v1 expectations.
3. Compute **breaking changes** diff (previous schema → current schema).
4. Score **ticket satisfaction** (did the agent implement the current ticket?).
5. Compute shaped reward (Section 5).
6. Emit next ticket (or none) and a contract/breaking report in the observation.

### Termination
Episode ends when either:
- All tickets satisfied AND contract pass rate is high (e.g., 1.0), OR
- `MAX_ITERATIONS` reached.

Anti-gaming requirement:
- Deleting endpoints should immediately fail contract checks and reduce reward.

---

## 3) Agent prompt (full structure)

### SYSTEM PROMPT
You are an expert API platform engineer. Your job is to iteratively evolve an OpenAPI 3.0/3.1 schema over multiple steps while maintaining backward compatibility for existing clients.

Hard constraints:
- Output MUST be valid JSON only (no markdown, no commentary).
- Output MUST be a complete OpenAPI schema object.
- NEVER remove existing endpoints, operations, or response fields used by clients unless explicitly instructed and a safe migration path exists.
- Prefer additive changes (new endpoints, new optional fields) over breaking changes.
- Versioning rules:
  - Keep v1 stable (do not break).
  - If a breaking change is required, introduce v2 endpoints while keeping v1 endpoints working.
- Security:
  - Every operation must be protected by a security scheme (global or per-operation).
- Deprecation:
  - Use OpenAPI `deprecated: true` when asked to deprecate.
  - Deprecated endpoints must remain functional.
- Documentation:
  - Provide summaries/descriptions for operations.

You will receive:
1) Baseline schema (current working schema you must evolve)
2) A change ticket to implement
3) A contract test report of what clients require + what broke
4) Validator feedback and errors

Goal: maximize contract pass rate + satisfy tickets with minimal breaking changes.

Return ONLY the updated OpenAPI schema JSON.

### USER MESSAGE TEMPLATE (each step)
BASELINE_SCHEMA_JSON:
<full JSON schema>

ACTIVE_TICKET:
<ticket text>

CONTRACT_TEST_REPORT:
- Missing required operations: [...]
- Response field regressions: [...]
- Auth regressions: [...]
- Notes: [...]

VALIDATION_FEEDBACK:
- validity_score: <0..1>
- best_practices_score: <0..1>
- errors (top N):
  - <severity>: <message> | suggestion: <suggestion>

Return ONLY valid JSON.

---

## 4) Contract suite + breaking change detection

### Contract suite (generated at reset)
Minimal but meaningful:
- `required_operations`: list of (path, method) pairs that must exist (3–8 ops)
- `required_security`: ensure global or per-op security exists for required ops
- `required_response_fields`: for key ops, enforce a few stable response JSON fields
  - Example item: `{path:"/v1/orders", method:"get", status:"200", fields:["id","status","total"]}`

### Contract evaluation (each step)
- Fail if a required (path,method) missing.
- Fail if security removed for required ops.
- Fail if required response fields removed (or type changed if you implement type-checking).

Return:
- `contract_pass_rate` in [0,1]
- list of `contract_failures` strings for agent feedback

### Breaking change detector (diff-based)
Count breaking changes between last schema and current schema:
- removed path / removed operation
- removed response status code
- removed schema property / changed property type
- optional→required field changes

Return:
- `breaking_change_count`
- `breaking_changes` list (human-readable)

Penalty:
- `breaking_penalty = min(0.5, 0.05 * breaking_change_count)`
- extra penalty if breaking touches contract-critical ops

---

## 5) Reward (dense, coherent)
Let:
- C = contract_pass_rate (0..1)
- T = ticket_score (0..1)
- Q = validator quality = 0.55*validity_score + 0.45*best_practices_score
- P = progress delta over previous step on (C+T)/2
- K = breaking_penalty + behavior_penalty

Reward:
R = 0.45*C + 0.25*T + 0.20*Q + 0.10*P - K
Clamp to [0,1].

Behavior penalties:
- repeated schema: +0.10
- no progress (P < 0.01 after step 2): +0.05
- mass deletion heuristic:
  - if operation count drops by >= 20% vs previous step, add `0.10 + 0.50*(drop_ratio-0.20)` capped at +0.30

Penalty caps (for stability):
- breaking_penalty: 0.05 per breaking change, capped at 0.50
- behavior_penalty: capped at 0.25

---

## 6) Tickets (long-horizon story engine)
Reveal one ticket at a time; types:

Additive (easy):
- Add endpoint: POST /v1/refunds
- Add pagination params to GET list endpoints
- Add 429 rate-limit response pattern

Deprecation/migration (hard, lifecycle):
- Deprecate v1 query endpoint, introduce v2 search endpoint
- Rename field: keep v1 output stable, add v2 output field, document deprecation

Security/compliance:
- Add RBAC scopes for admin endpoints
- Add audit log endpoint + document audit behavior

Ticket scoring:
- Deterministic checklist per ticket (presence of endpoints/params/responses/security/deprecation flags)
- Output `ticket_score` in [0,1] + `ticket_feedback`

---

## 7) Training plan (RTX 4070 laptop, 8GB VRAM)

### Model choice
- Preferred: Qwen2.5-1.5B-Instruct (QLoRA 4-bit)
- Optional if fits: Qwen2.5-3B-Instruct (QLoRA 4-bit)

### Method (cheap + reliable)
1) SFT warmstart (Unsloth): teach strict JSON + OpenAPI skeletons + “fix based on feedback”.
2) Best-of-N rollout collection with rule-based reward:
   - sample N=2–4 candidates per step
   - keep highest reward trajectory
   - log (prompt → best schema) pairs
3) SFT again on collected trajectories
4) Iterate 2–4 times
5) Evaluate baseline vs trained on fixed seeds; plot:
   - avg reward
   - avg contract_pass_rate
   - avg breaking_change_count

HF credits ($30):
- Use only for final evaluation (optional), e.g., 50 episodes * 1 call per episode end.
- Do NOT use HF as per-step judge during training.

### Resumable training & checkpoints (must-have)
Training on Colab/HF can be interrupted. Make the pipeline resumable by checkpointing **both** model weights and collected rollouts.

#### A) Model checkpoints (LoRA adapter + trainer state)
- Save to a persistent location:
  - Colab: Google Drive (recommended), e.g. `/content/drive/MyDrive/<project>/checkpoints/...`
  - HF: push checkpoints to a private model repo on Hugging Face Hub
- Save frequently:
  - `save_steps`: 50–200
  - `save_total_limit`: 2–5
- Each checkpoint folder should include:
  - LoRA adapter weights
  - tokenizer files
  - trainer state (optimizer/scheduler/random states) so resume is stable

#### B) Rollout/dataset checkpoints (don’t lose collected samples)
- When generating best-of-N trajectories, append examples to JSONL continuously:
  - `data/rollouts_iter000.jsonl`, `data/rollouts_iter001.jsonl`, ...
- Maintain a progress file updated every episode (or every few steps):
  - `data/progress.json` with fields like: `iteration`, `episode_idx`, `env_seed`, `last_checkpoint_path`

#### Resume procedure (Colab / Drive)
1) Mount Drive.
2) Locate the latest checkpoint directory (highest step).
3) Restart training with `resume_from_checkpoint=<checkpoint_path>`.
4) Continue rollout collection from `data/progress.json` and keep appending to the JSONL files.

#### Resume procedure (HF Hub / Space)
- During training, periodically push checkpoints:
  - `push_to_hub=True`
  - `hub_strategy="checkpoint"` (push intermediate checkpoints)
- On restart:
  - pull the latest checkpoint from the Hub repo
  - restart training with `resume_from_checkpoint=<downloaded_checkpoint_path>`

#### Minimum proof for judges
- Include at least one plot/metric file (e.g., `metrics.csv`) that shows training continued after interruption (two runs appended to the same curve).

---

## 8) Deliverables for judges
- HF Space runs the environment.
- Minimal training script / Colab using Unsloth (+ optional TRL, but best-of-N + SFT is acceptable if it demonstrates improvement).
- README includes:
  - Problem, environment mechanics, reward
  - Before/after episode example
  - Plots: reward curve + contract pass rate + breaking changes

---

## 9) Implementation map (based on current codebase shape)
- Extend environment logic: server environment file (reset/step/state)
- Add graders:
  - ContractSuiteGrader
  - TicketSatisfactionGrader
  - BreakingChangeDetector
- Reuse existing:
  - ValidationPipeline (JSON/OpenAPI/Auth/BestPractices)
  - RewardCalculator shaping style
