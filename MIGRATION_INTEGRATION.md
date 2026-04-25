# MigrationEnvironment Integration Guide

## Overview

The `MigrationEnvironment` seamlessly integrates with the existing API Conformance Gym codebase, reusing core components while extending functionality for API evolution scenarios. This document describes the integration points and how to use the migration environment alongside the existing conformance environment.

## Integration Points

### 1. ValidationPipeline Integration (Requirement 9.2)

The `MigrationEnvironment` reuses the existing `ValidationPipeline` component for schema quality scoring:

```python
# In MigrationEnvironment.__init__() (inherited from APIEnvironment)
self._validation_pipeline = ValidationPipeline()

# In MigrationEnvironment.step()
validation_result = self._validation_pipeline.validate(action.schema_json)
```

**Benefits:**
- Consistent validation logic across both environments
- No code duplication
- Maintains compatibility with existing validation patterns
- Provides detailed error feedback for agent learning

**Validation Components Used:**
- `JSONParser` - Validates JSON structure and syntax
- `OpenAPIValidator` - Checks OpenAPI 3.0/3.1 compliance
- `AuthValidator` - Validates security schemes and endpoint protection
- `BestPracticesChecker` - Evaluates API design best practices

### 2. Reward Calculation Integration (Requirement 9.3)

The `MigrationRewardCalculator` extends existing reward calculation patterns:

```python
# Multi-component reward calculation
reward = MigrationRewardCalculator.calculate_reward(
    contract_pass_rate=contract_result.contract_pass_rate,      # 45%
    ticket_score=ticket_score,                                   # 25%
    validity_score=validation_result.validity_score,             # 20% (part of quality)
    best_practices_score=validation_result.best_practices_score, # 20% (part of quality)
    progress_delta=progress_delta,                               # 10%
    breaking_penalty=breaking_report.breaking_penalty,           # Subtracted
    behavior_penalty=penalty,                                    # Subtracted
)
```

**Compatibility:**
- Uses same reward range [0.0, 1.0] as `RewardCalculator`
- Follows established penalty subtraction patterns
- Maintains reward clamping behavior
- Compatible with existing grading infrastructure

### 3. Environment Registration and Configuration (Requirement 9.4, 9.5)

The migration environment is registered through the configuration system:

#### Configuration System (`grading_config.py`)

```python
# Create migration environment with configuration
from grading_config import create_migration_env

# Development configuration
dev_env = create_migration_env(environment="development")

# Production configuration
prod_env = create_migration_env(environment="production")

# Custom configuration
custom_env = create_migration_env(
    environment="hackathon",
    use_llm_grading=True,
    timeout=20.0
)
```

#### Environment Type Selection

```python
from grading_config import create_development_env

# Create API conformance environment
api_env = create_development_env(env_type="api")

# Create migration environment
migration_env = create_development_env(env_type="migration")
```

#### FastAPI Application (`server/migration_app.py`)

The migration environment has its own FastAPI application endpoint:

```bash
# Run migration environment server
uvicorn server.migration_app:app --host 0.0.0.0 --port 8001

# Run API conformance environment server (original)
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

#### OpenEnv Configuration (`openenv_migration.yaml`)

The migration environment has its own OpenEnv configuration:

```yaml
spec_version: 1
name: api_lifecycle_migration
type: space
runtime: fastapi
app: server.migration_app:app
port: 8001
```

## Coexistence with APIEnvironment

Both environments can run simultaneously without conflicts:

```python
from server.api_conformance_gym_environment import APIEnvironment
from server.migration_environment import MigrationEnvironment

# Create both environment types
api_env = APIEnvironment()
migration_env = MigrationEnvironment()

# Reset both independently
api_obs = api_env.reset(seed=42)
migration_obs = migration_env.reset(seed=42)

# Different observation structures
assert hasattr(migration_obs, 'baseline_schema_json')  # Migration-specific
assert not hasattr(api_obs, 'baseline_schema_json')    # Not in API env

assert hasattr(migration_obs, 'contract_test_report')  # Migration-specific
assert not hasattr(api_obs, 'contract_test_report')    # Not in API env
```

**Key Differences:**

| Feature | APIEnvironment | MigrationEnvironment |
|---------|---------------|---------------------|
| Base task | Design new API from requirements | Evolve existing API |
| Observation | APIObservation | MigrationObservation |
| Action | APIAction | MigrationAction |
| Reward components | Quality + Task + Progress | Contract + Ticket + Quality + Progress |
| Episode length | 10 iterations | 15 iterations |
| Termination | Max iterations or perfect schema | All tickets done or max iterations |

## Usage Examples

### Example 1: Basic Migration Environment Usage

```python
from grading_config import create_migration_env
from migration_models import MigrationAction
import json

# Create environment
env = create_migration_env()

# Reset with baseline schema
obs = env.reset(seed=42)

print(f"Baseline schema: {obs.baseline_schema_json[:100]}...")
print(f"Active ticket: {obs.active_ticket.title}")
print(f"Contract requirements: {len(obs.contract_test_report.contract_failures)}")

# Evolve schema
baseline = json.loads(obs.baseline_schema_json)
evolved = baseline.copy()
evolved["info"]["version"] = "1.1.0"

action = MigrationAction(schema_json=json.dumps(evolved))
obs = env.step(action)

print(f"Contract pass rate: {obs.contract_test_report.contract_pass_rate}")
print(f"Ticket satisfaction: {obs.ticket_satisfaction_score}")
print(f"Reward: {obs.reward}")
```

### Example 2: Using Configuration Presets

```python
from grading_config import (
    create_development_env,
    create_production_env,
    create_hackathon_env
)

# Development: LLM grading enabled, longer timeout
dev_env = create_development_env(env_type="migration")

# Production: Rule-based grading, shorter timeout
prod_env = create_production_env(env_type="migration")

# Hackathon: LLM grading with higher innovation weight
hackathon_env = create_hackathon_env(env_type="migration")
```

### Example 3: Running Both Environments Concurrently

```python
from grading_config import create_development_env

# Create both environment types
api_env = create_development_env(env_type="api")
migration_env = create_development_env(env_type="migration")

# Run episodes independently
api_obs = api_env.reset(seed=42)
migration_obs = migration_env.reset(seed=43)

# Both environments maintain independent state
print(f"API episode: {api_obs.episode_info['episode_id']}")
print(f"Migration episode: {migration_obs.episode_info['episode_id']}")
```

## Testing Integration

Run integration tests to verify all components work together:

```bash
# Run all integration tests
python -m pytest test_migration_integration.py -v

# Run specific test class
python -m pytest test_migration_integration.py::TestValidationPipelineIntegration -v

# Run integration demo
python examples/migration_integration_demo.py
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Existing Codebase                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │ ValidationPipeline│         │ RewardCalculator │        │
│  │  - JSONParser     │         │  - calculate()   │        │
│  │  - OpenAPIValidator│        │  - calculate_    │        │
│  │  - AuthValidator  │         │    shaped()      │        │
│  │  - BestPractices  │         └──────────────────┘        │
│  └──────────────────┘                   ▲                  │
│           ▲                              │                  │
│           │                              │                  │
│           │         ┌────────────────────┴────────┐        │
│           │         │                             │        │
│  ┌────────┴─────────┴──────┐    ┌────────────────┴─────┐  │
│  │   APIEnvironment        │    │ MigrationEnvironment │  │
│  │   - reset()             │    │ - reset()            │  │
│  │   - step()              │    │ - step()             │  │
│  │   - state               │    │ - state              │  │
│  └─────────────────────────┘    └──────────────────────┘  │
│           │                              │                  │
│           │                              │                  │
│  ┌────────┴─────────┐          ┌────────┴──────────────┐  │
│  │  APIAction       │          │  MigrationAction      │  │
│  │  APIObservation  │          │  MigrationObservation │  │
│  └──────────────────┘          └───────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              │
                    ┌─────────┴──────────┐
                    │  grading_config.py │
                    │  - create_env()    │
                    │  - configurations  │
                    └────────────────────┘
```

## Key Integration Benefits

1. **Code Reuse**: ValidationPipeline and reward calculation patterns are reused
2. **Consistency**: Same validation logic ensures consistent quality standards
3. **Flexibility**: Configuration system allows easy switching between environments
4. **Coexistence**: Both environments can run simultaneously without conflicts
5. **Maintainability**: Changes to core components benefit both environments
6. **Extensibility**: New environment types can follow the same integration pattern

## Requirements Satisfied

- **Requirement 5.1**: Evolved schemas validated by ValidationPipeline for OpenAPI compliance
- **Requirement 5.2**: Quality scores calculated from validity and best practices metrics
- **Requirement 5.3**: Detailed error feedback provided when schemas fail validation
- **Requirement 9.2**: Reuse existing ValidationPipeline component
- **Requirement 9.3**: Maintain compatibility with existing grading and reward calculation patterns
- **Requirement 9.4**: Coexist with existing conformance testing environments
- **Requirement 9.5**: Follow established patterns for environment registration and configuration
