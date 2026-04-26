# Vision & Motivation

Building APIs is easy. Evolving them safely is hard.

That is the heart of this project. In real teams, a v1 API already has consumers in production, and every "small" change carries risk: clients break, auth coverage regresses, and platform trust drops. We built an environment where an RL agent must operate under that same pressure - move the system forward while preserving what already works.

This is not a toy benchmark about generating a schema once. It is a long-horizon migration task about compatibility, sequencing, and disciplined change.

# The Real Problem

API lifecycle work sits at the intersection of product speed and operational safety:
- product wants new features now
- security wants stronger enforcement now
- compliance wants better documentation now
- existing clients want zero breakage

Humans struggle with this balance. LLM agents struggle even more when feedback is sparse or one-dimensional.

# Why Existing Systems Fail

Typical schema-generation benchmarks fail to represent production migration:
- no baseline contract that must survive
- no multi-step ticket progression
- no explicit breaking-change accounting
- no dense reward for "progress without regressions"

So models can score well while still learning unsafe habits (e.g., deleting paths to simplify outputs).

# Previous Failure Modes

This codebase targets concrete failure patterns observed in prior iterations:
- reward instability from out-of-range reward composition (documented bugfix spec)
- policy collapse patterns (oscillating rewards, KL spikes, completion collapse)
- malformed JSON outputs that poison training signal
- step-level wins that still break long-term compatibility

The environment and training stack were redesigned so these are directly penalized or filtered.

# Our Core Insight

Treat API evolution as a **contract-preserving control problem**, not a formatting problem.

The agent is repeatedly asked: "Can you satisfy this migration task **without breaking existing client expectations**?"  
That single framing creates meaningful pressure for planning, cautious edits, and recovery behavior.

# Why This Is Hard for LLMs

LLMs are naturally biased toward local completion quality, but this environment requires:
- remembering baseline invariants across steps
- balancing multiple objectives with conflicting gradients
- avoiding tempting shortcuts (remove old ops, overfit to current ticket)
- returning strict machine-parseable JSON every time

This is long-horizon instruction following with hard structural constraints.

# Environment Design

The environment extends the existing API Conformance Gym into an API lifecycle migration simulator:
- baseline v1 schema selected at reset
- deterministic contract suite generated from that baseline
- progressive migration tickets (additive, security, compliance, deprecation)
- per-step validation, contract testing, breaking-change diffing, ticket scoring, and shaped reward

Design source of truth is the migration spec/design under `.kiro/specs/api-lifecycle-migration/`.

# OpenEnv Interface Importance

One reason this environment matters beyond a single demo is that it is implemented as a proper OpenEnv environment with the canonical three-method interaction contract:

| OpenEnv method | What it does in this project | Why it matters for judges and training |
|---|---|---|
| `reset()` | Initializes a new episode with baseline v1 schema, generated contract suite, and first migration ticket | Ensures repeatable scenario starts and clean long-horizon evaluation boundaries |
| `step(action)` | Accepts evolved schema JSON and runs validation, contract tests, breaking-change detection, ticket scoring, and reward shaping | Concentrates all learning pressure in one deterministic feedback loop, which is the core innovation |
| `state` | Exposes current environment metadata/state for runtime inspection | Improves debuggability, reliability, and confidence that training behavior is not a black box |

In practical terms, these three methods make the environment portable, benchmarkable, and trainable across different agents and infrastructure - not just handcrafted for one script.

# Environment Mechanics

## Situation -> Task -> Action -> Result (STAR loop)

- **Situation:** baseline v1 API with client expectations
- **Task:** satisfy active migration ticket
- **Action:** submit full evolved OpenAPI schema JSON
- **Result:** receive rich feedback (contract pass, ticket score, quality score, penalties, next ticket)

This repeats until all tickets are completed with high contract preservation or max iterations reached.

# State Space

Core state/observation elements include:
- `baseline_schema_json` (immutable reference)
- `active_ticket` and ticket queue progress
- `contract_test_report` (pass rate + detailed failures)
- `breaking_change_report` (count, typed list, penalty)
- validation signals (`validity_score`, `best_practices_score`, errors)
- episode metadata (`iteration`, `step_count`, termination reason, etc.)

This state is intentionally rich so policy improvement has dense, actionable signal.

# Action Space

The action is deliberately simple and strict:
- `schema_json` (complete evolved OpenAPI object as JSON string)
- optional migration notes
- iteration metadata

Constraint: agent must output a full machine-usable schema every step, not patches or prose.

# Reward System

Migration reward is explicitly multi-objective:

\[
R = 0.45C + 0.25T + 0.20Q + 0.10P - B - K
\]

Where:
- `C`: contract preservation pass rate
- `T`: ticket satisfaction score
- `Q`: quality score from validity + best-practices
- `P`: positive progress delta
- `B`: breaking-change penalty
- `K`: behavior penalty (e.g., repeated/no-progress behavior)

Final reward is clamped to `[0, 1]`.

# Reward Shaping Decisions

Why this shaping works:
- **Contract-heavy weighting (45%)** prevents ticket-chasing via regressions.
- **Ticket weight (25%)** keeps migration task completion meaningful.
- **Quality weight (20%)** rewards production-grade schema hygiene.
- **Progress delta (10%)** creates smoother learning signal across trajectory.
- **Penalty caps** prevent collapse from over-punishment while still discouraging unsafe behavior.

# Failure Recovery Design

Robustness choices are explicit in implementation:
- invalid JSON produces descriptive error observations (no environment crash)
- fallback reports when subcomponents fail (contract/breaking/ticket scoring exceptions)
- stable zero/low reward paths for malformed actions
- logging-rich error handling to preserve training continuity

# Exploration Challenges

The agent must explore without violating safety constraints:
- additive changes are safer but may under-satisfy harder tickets
- aggressive edits can satisfy immediate tickets but trigger contract/breaking penalties
- deterministic scoring can still create local maxima around "good enough"

The environment therefore rewards incremental safe progress, not flashy one-step rewrites.

# Training Strategy

The training strategy in this repo combines structure-first reliability with environment reward:

1. **Strict JSON discipline** (parser-based reliability rewards)
2. **Environment-grounded reward** (actual `env.step()` reward in training reward function)
3. **Optional SFT warmstart** for schema format/task priors
4. **GRPO optimization** with multi-generation sampling
5. **Reliability evaluation + composite checkpoint ranking**

This is appropriate because it addresses both failure channels:
- generation-format failure (can't parse / invalid OpenAPI)
- task failure (doesn't preserve contract or satisfy ticket)

# Training Process

Implemented pipeline (from `training/training_converted.py`):
- collect prompt dataset from environment resets
- optionally build SFT examples from heuristic teacher policy
- define dual reward functions:
  - JSON reliability reward
  - environment step reward (dominant task signal)
- train via GRPO with checkpointing and resumability
- export logs/artifacts and run baseline-vs-trained comparison

## Exploration vs Exploitation

- **Exploration:** stochastic generation during training (`temperature`, `top_p`, multiple generations)
- **Exploitation:** strict scoring gate + deterministic validation path + reward on true env behavior
- **Control:** explicit penalties for malformed output, truncation symptoms, and no-progress loops

# Curriculum or Sampling Strategy

Current curriculum is implicit and episode-driven:
- repeated resets with seeded scenarios
- ticket progression inside each episode (easy -> medium/harder migration tasks)
- mixed task types force capability breadth (additive/security/compliance/deprecation)

Future extension: explicit staged curriculum by ticket difficulty and schema complexity.

# Why This Environment Produces Learning Pressure

This environment creates real pressure because no single trick solves it:
- pure syntax optimization fails contract checks
- pure ticket chasing triggers breaking penalties
- conservative no-change behavior stalls progress and earns low reward
- malformed outputs get punished before task success is even possible

The highest reward path requires joint optimization under constraint - exactly the capability we want.

# What Behaviors We Wanted to Train

Target behaviors:
- preserve baseline client-critical operations and response fields
- implement requested migration changes with minimal disruption
- maintain or improve auth and documentation quality
- recover from failed attempts using feedback
- produce strict, parseable, complete JSON every step

# Technical Architecture

System layers:
- **Environment server (FastAPI/OpenEnv):** episode orchestration and concurrency
- **Validation pipeline:** JSON/OpenAPI/Auth/Best-practices checks
- **Contract grader:** baseline-derived invariant enforcement
- **Breaking change detector:** schema diff -> change list + penalty
- **Ticket grader/progression:** task satisfaction and next-ticket control
- **Reward calculator:** weighted aggregation + penalties + clamping
- **Client/inference/training:** policy rollouts, reward calls, logging, evaluation

# Key Engineering Decisions

- Reuse existing validation infrastructure from API Conformance Gym
- Introduce migration-specific models and observation richness
- Keep scoring deterministic where possible for stable RL signal
- Use server-side reward logic to reduce reward hacking
- Add reliability utilities for strict parsing and controlled repair fallback
- Build resumable training/checkpoint flow for interrupted runs

# Tradeoffs and Constraints

| Decision | Benefit | Tradeoff |
|---|---|---|
| Full-schema action (not patch) | Simpler action semantics, easier deterministic grading | Higher token cost, longer outputs |
| Strong contract weighting | Prevents unsafe migration shortcuts | Can slow aggressive feature exploration |
| Strict JSON parsing in training reward | Cleaner optimization signal | Harsh penalties early in training |
| Deterministic ticket heuristics | Reproducible scoring | May under-capture nuanced semantic intent |
| Capped penalties | Avoids reward collapse | Can under-penalize extreme bad actions |

# Evaluation Methodology

Implemented evaluation modalities include:
- per-step environment reward traces
- reliability metrics (strict parse rate, truncation, markdown fence rate)
- OpenAPI validation pass rate
- ticket success and contract preservation rates
- breaking-change rate
- baseline heuristic vs trained policy comparisons on fixed seeds

# Observable Learning Signals

Signals this setup is designed to improve over training:
- higher strict JSON parse success
- fewer truncated/malformed outputs
- improved mean reward per episode
- higher ticket satisfaction with contract preservation retained
- lower average breaking change count

These are directly measured in the training notebook pipeline and exported artifacts.

# Training Results (placeholder if needed)

**Placeholder: insert finalized run metrics from artifacts/logs.**

Recommended inserts:
- final `mean_reward`, `total_reward`, and success rate over fixed eval seeds
- best checkpoint by composite reliability score
- before/after contract preservation and ticket success rates

# Reward Progression (placeholder if needed)

**Placeholder: insert reward curve plot(s).**

Suggested plot set:
- training step vs reward
- reward std over steps
- KL vs steps (for stability monitoring)
- completion length vs steps

# Before vs After Behavior (placeholder if needed)

**Placeholder: insert paired episode traces (baseline policy vs trained policy).**

Recommended evidence:
- same seed, same ticket sequence
- side-by-side:
  - contract pass rate trajectory
  - ticket satisfaction trajectory
  - breaking changes introduced
  - final mean episode reward

# Deliverables

Current project deliverables include:
- OpenEnv-compatible migration environment server
- typed action/observation/state models
- contract grader, breaking change detector, ticket grader, progression manager
- multi-component reward implementation
- baseline inference script for hackathon format
- training notebook/script with GRPO + reliability instrumentation
- evaluation and artifact export pipeline

# Limitations

Honest limitations in current form:
- baseline schema pool is small (limited domain diversity)
- ticket grading logic is heuristic/string-pattern based for some criteria
- contract suite generation currently prioritizes core response fields, not full semantic schemas
- no external live integration tests against real downstream clients
- final judged metrics are run-dependent and must be filled from actual artifacts

# Future Work

High-impact next steps:
- expand baseline schema library across domains and complexity tiers
- enrich deprecation/versioning tickets with stronger long-horizon dependencies
- add semantic diff checks (types, required/optional transitions, compat classes)
- introduce stochastic client simulation for stronger contract realism
- add richer curriculum scheduling and difficulty-adaptive sampling

# Why This Matters

This environment pushes beyond "can a model output JSON?" toward "can an agent evolve production interfaces responsibly over time?"

That distinction matters for real adoption. Enterprises do not need models that can draft APIs once. They need agents that can change systems safely, step by step, under constraints that mirror platform engineering reality.

By embedding backward compatibility, ticket-driven migration, breaking-change accountability, and reward-stable training into one loop, this project creates meaningful learning pressure for precisely that capability.

