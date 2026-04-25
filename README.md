---
title: API Lifecycle Migration Environment
emoji: 🔄
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 7860
tags:
  - openenv
  - api-evolution
  - migration
  - backward-compatibility
  - reinforcement-learning
  - hackathon
---

# API Lifecycle Migration Environment

**Train RL agents on API evolution scenarios with backward compatibility preservation.**

The API Lifecycle Migration Environment is a production-ready OpenEnv environment for the 2026 Meta PyTorch Hackathon. It trains reinforcement learning agents to evolve v1 OpenAPI schemas while preserving backward compatibility, managing breaking changes, and satisfying progressive migration tickets.

## 🎯 Environment Description & Motivation

The API Lifecycle Migration Environment addresses the critical challenge of API evolution - how to add new features, improve security, and enhance documentation while maintaining backward compatibility for existing clients.

**Why API Migration Matters:**
- APIs must evolve without breaking existing integrations
- Breaking changes cost millions in client downtime and support
- Manual migration planning is error-prone and time-intensive
- Industry lacks standardized training for API lifecycle management

**Real-World Impact:**
This environment simulates actual API evolution scenarios that platform engineers face daily:

- **Additive Changes** - Adding new endpoints, optional fields, pagination
- **Security Enhancements** - Adding authentication, RBAC, audit logging
- **Deprecation Management** - Marking old endpoints deprecated while maintaining v1
- **Breaking Changes** - Introducing v2 endpoints when necessary while keeping v1 stable
- **Documentation Improvements** - Enhancing API docs and compliance
- **Contract Preservation** - Ensuring existing clients continue to work

Agents learn to evolve OpenAPI schemas progressively through ticket-based tasks while maximizing contract test pass rates and minimizing breaking changes.

## 🚀 Setup and Usage Instructions

### Prerequisites
- Python 3.11+ with conda/miniconda installed
- Docker (for containerized deployment)
- Git for cloning the repository

### Environment Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd api_lifecycle_migration
```

2. **Activate the conda environment:**
```bash
conda activate openenv
```

3. **Install dependencies:**
```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r server/requirements.txt
```

### Quick Start

### Running Python Scripts

All Python scripts should be run with the activated conda environment:

```bash
# Activate environment first
conda activate openenv

# Run the baseline inference script
python inference.py

# Run quick test
python quick_test.py

# Start the server
python start_server.py
```

### Using the Client

```python
from client import MigrationEnvClient
from migration_models import MigrationAction
import json

# Connect to environment
with MigrationEnvClient(base_url="http://localhost:7860") as env:
    # Reset to get baseline schema and first ticket
    result = env.reset()
    obs = result.observation
    
    print(f"Baseline schema: {obs.baseline_schema_json[:100]}...")
    print(f"Active ticket: {obs.active_ticket.title}")
    print(f"Contract pass rate: {obs.contract_test_report.contract_pass_rate}")
    
    # Submit evolved schema
    baseline = json.loads(obs.baseline_schema_json)
    # ... modify baseline to satisfy ticket ...
    
    action = MigrationAction(schema_json=json.dumps(baseline), iteration=1)
    result = env.step(action)
    
    print(f"Reward: {result.reward:.2f}")
    print(f"Ticket score: {result.observation.ticket_satisfaction_score:.2f}")
    print(f"Breaking changes: {result.observation.breaking_change_report.breaking_change_count}")
```

### Using Docker

```bash
# Build the environment
docker build -t api-lifecycle-migration:latest .

# Run the server
docker run -p 7860:7860 api-lifecycle-migration:latest
```

### Using the Baseline Inference Script

The environment includes a hackathon-compliant inference script:

```bash
# Set required environment variables
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-Coder-3B-Instruct"
export HF_TOKEN="your-hugging-face-token"
export ENV_SERVER_URL="http://localhost:7860"

# Run the baseline
python inference.py
```

Expected output format:
```
[START] task=api-lifecycle-migration env=api_lifecycle_migration model=Qwen2.5-Coder-3B-Instruct
[STEP] step=1 action={"openapi":"3.0.0",...} reward=0.55 done=false error=null
[STEP] step=2 action={"openapi":"3.0.0",...} reward=0.72 done=false error=null
[STEP] step=3 action={"openapi":"3.0.0",...} reward=0.85 done=true error=null
[END] success=true steps=3 score=0.707 rewards=0.55,0.72,0.85
```

## 🏆 Hackathon Compliance

This environment meets all 2026 Meta PyTorch Hackathon requirements:

### ✅ Real-World Task Simulation
- Simulates actual API evolution tasks platform engineers perform daily
- Progressive ticket-based migration scenarios
- Backward compatibility preservation requirements
- Not games or toy problems

### ✅ OpenEnv Spec Compliance
- Full OpenEnv interface with typed Action, Observation models
- Standard `reset()`, `step()`, and `state()` primitives
- Tested via `openenv validate`

### ✅ Multi-Component Reward Function
Balanced reward formula providing signal across the full trajectory:

**R = (0.45 × C) + (0.25 × T) + (0.20 × Q) + (0.10 × P) - B - K**

Where:
- **C** = Contract preservation pass rate (0.0-1.0): Backward compatibility
- **T** = Ticket satisfaction score (0.0-1.0): Task completion
- **Q** = Schema quality score (0.0-1.0): Validity + best practices
- **P** = Progress improvement delta (0.0-1.0): Positive trajectory
- **B** = Breaking change penalty: Penalizes API breaking changes
- **K** = Behavior penalty: Penalizes repeated schemas, no progress

**Reward Range**: [0.0, 1.0]

### ✅ Baseline Inference Script
- Uses OpenAI Client with environment variables (API_BASE_URL, MODEL_NAME, HF_TOKEN)
- Emits required stdout format: [START], [STEP], [END] lines
- Produces reproducible baseline scores

## 🔧 Environment Details

### Action Space
**MigrationAction**: Agent submits evolved OpenAPI schema designs
- `schema_json` (str): JSON-stringified evolved OpenAPI 3.0/3.1 schema
- `iteration` (int): Current iteration number for tracking progress
- `migration_notes` (str, optional): Agent notes about migration strategy

**Action Constraints:**
- Schema must be valid JSON format
- Must conform to OpenAPI 3.0 or 3.1 specification
- Should maintain backward compatibility with baseline schema
- Iteration tracking enables multi-turn learning

### Observation Space  
**MigrationObservation**: Comprehensive migration feedback
- `baseline_schema_json` (str): Original v1 schema to maintain compatibility with
- `active_ticket` (MigrationTicket): Current migration ticket with acceptance criteria
- `contract_test_report` (ContractTestResult): Backward compatibility test results
- `breaking_change_report` (BreakingChangeReport): Breaking changes detected
- `ticket_satisfaction_score` (float): Score for current ticket (0.0-1.0)
- `tickets_completed` (int): Number of tickets completed
- `total_tickets` (int): Total number of tickets in queue
- `validation_errors` (List[ValidationError]): Schema validation errors
- `error_count` (int): Total validation error count
- `validity_score` (float): OpenAPI specification compliance (0.0-1.0)
- `best_practices_score` (float): API design best practices (0.0-1.0)
- `schema_feedback` (str): Human-readable feedback summary
- `iteration` (int): Current iteration number (1-15)
- `episode_info` (dict): Episode metadata and statistics
- `episode_done` (bool): Whether episode is complete

### Ticket Types

1. **Additive Tickets** - Add new endpoints, fields, or features
   - Example: "Add book reviews endpoint with GET and POST methods"
   - Difficulty: Easy to Medium

2. **Security Tickets** - Enhance API security and authentication
   - Example: "Ensure all endpoints have proper authentication"
   - Difficulty: Medium

3. **Compliance Tickets** - Improve documentation and standards
   - Example: "Add comprehensive descriptions and examples"
   - Difficulty: Medium

4. **Deprecation Tickets** - Mark old endpoints as deprecated
   - Example: "Deprecate v1 query endpoint, introduce v2 search"
   - Difficulty: Hard

## 🔍 Validation & Grading Pipeline

The environment uses a comprehensive multi-component grading system:

### 1. Contract Suite Grader
- Generates contract expectations from baseline v1 schema
- Tests for missing operations, response field regressions, auth regressions
- Returns contract pass rate [0.0, 1.0]

### 2. Breaking Change Detector
- Detects breaking changes between schema versions
- Identifies removed paths, operations, fields, type changes
- Calculates breaking change penalty

### 3. Ticket Satisfaction Grader
- Evaluates schema against ticket acceptance criteria
- Different logic for additive, security, compliance, deprecation tickets
- Returns satisfaction score [0.0, 1.0]

### 4. Schema Validators
- JSON syntax validation
- OpenAPI 3.0/3.1 specification compliance
- Authentication and security validation
- Best practices checking

## 📊 Performance Targets & Baseline Scores

### Environment Performance
- **Reset latency**: <100ms (environment initialization)
- **Step latency**: <500ms (validation + reward calculation)  
- **State latency**: <50ms (state retrieval)
- **Concurrent agents**: 10+ simultaneous training sessions
- **Episode length**: Up to 15 iterations per episode

### Expected Reward Ranges
- **No changes** (baseline schema): 0.45-0.55 reward
- **Ticket partially satisfied**: 0.55-0.70 reward
- **Ticket satisfied, no breaking changes**: 0.70-0.85 reward
- **All tickets completed, high contract rate**: 0.85-1.0 reward

### Episode Termination
Episode ends when either:
- All tickets satisfied AND contract pass rate ≥ 95%, OR
- Maximum 15 iterations reached

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Layer                            │
│  ┌──────────────┐              ┌──────────────────────┐    │
│  │  RL Agent    │──────────────│ MigrationEnvClient   │    │
│  └──────────────┘              └──────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ WebSocket/HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      Server Layer                            │
│  ┌──────────────┐              ┌──────────────────────┐    │
│  │ FastAPI App  │──────────────│ MigrationEnvironment │    │
│  └──────────────┘              └──────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Grading Pipeline                           │
│  ┌──────────────────┐  ┌──────────────────────────┐        │
│  │ Contract Grader  │  │ Breaking Change Detector │        │
│  └──────────────────┘  └──────────────────────────┘        │
│  ┌──────────────────┐  ┌──────────────────────────┐        │
│  │ Ticket Grader    │  │ Validation Pipeline      │        │
│  └──────────────────┘  └──────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Deployment

### Hugging Face Spaces

Deploy directly to Hugging Face Spaces:

```bash
# Push to HF Spaces
git push https://huggingface.co/spaces/your-username/api-lifecycle-migration main
```

The environment will automatically start on port 7860 (HF Spaces default).

### Local Development

```bash
# Install dependencies
uv sync

# Run server
python start_server.py

# Or use uvicorn directly
uvicorn server.app:app --host 0.0.0.0 --port 7860

# Test with client
python debug_client.py
```

## 📁 Project Structure

```
api_lifecycle_migration/
├── README.md                           # This documentation
├── openenv.yaml                        # Environment manifest
├── Dockerfile                          # Container definition
├── inference.py                        # Hackathon baseline script
├── migration_models.py                 # Data models (Action, Observation, Tickets)
├── client.py                           # MigrationEnvClient for agent interaction
├── server/
│   ├── migration_environment.py        # Core environment logic
│   ├── app.py                          # FastAPI web interface
│   ├── contract_grader.py              # Contract suite generation & testing
│   ├── breaking_change_detector.py     # Breaking change detection
│   ├── ticket_grader.py                # Ticket satisfaction scoring
│   ├── ticket_progression.py           # Ticket queue management
│   ├── validators.py                   # 4-stage validation pipeline
│   ├── reward.py                       # Reward calculation
│   └── requirements.txt                # Python dependencies
└── tests/                              # Comprehensive test suite
```

## 🤝 Contributing

This environment was built for the 2026 Meta PyTorch Hackathon. The codebase follows OpenEnv standards and includes comprehensive testing.

Key design principles:
- **Server-side reward calculation** prevents reward hacking
- **Multi-turn episodes** allow iterative schema evolution
- **Contract-based testing** ensures backward compatibility
- **Progressive tickets** enable long-horizon planning
- **Deterministic grading** enables fair hackathon evaluation

## 📄 License

Copyright (c) Meta Platforms, Inc. and affiliates. Licensed under the BSD-style license.

## 🔗 Links

- [OpenEnv Documentation](https://github.com/meta-pytorch/OpenEnv)
- [OpenAPI Specification](https://spec.openapis.org/oas/v3.1.0)
- [Meta PyTorch Hackathon 2026](https://pytorch.org/hackathon)
