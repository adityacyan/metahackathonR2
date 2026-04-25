#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Demonstration of MigrationEnvironment integration with existing codebase.

This example shows how MigrationEnvironment integrates with:
1. ValidationPipeline for schema validation
2. MigrationRewardCalculator for reward calculation
3. Existing grading and configuration infrastructure
"""

import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grading_config import (
    create_migration_env,
    create_development_env,
    create_production_env,
)
from migration_models import MigrationAction


def demo_basic_integration():
    """Demonstrate basic integration with existing components."""
    print("=" * 80)
    print("Demo 1: Basic Integration with ValidationPipeline and RewardCalculator")
    print("=" * 80)
    
    # Create migration environment using configuration system
    env = create_migration_env(environment="development")
    
    print("\n1. Environment created successfully")
    print(f"   - Type: {type(env).__name__}")
    print(f"   - Supports concurrent sessions: {env.SUPPORTS_CONCURRENT_SESSIONS}")
    print(f"   - Max iterations: {env.MAX_ITERATIONS}")
    
    # Reset environment
    obs = env.reset(seed=42)
    
    print("\n2. Environment reset complete")
    print(f"   - Episode ID: {obs.episode_info['episode_id']}")
    print(f"   - Active ticket: {obs.active_ticket.title}")
    print(f"   - Contract requirements: {len(obs.contract_test_report.contract_failures)} operations")
    
    # Submit evolved schema
    baseline = json.loads(obs.baseline_schema_json)
    evolved = baseline.copy()
    evolved["info"]["version"] = "1.1.0"
    
    action = MigrationAction(schema_json=json.dumps(evolved))
    obs = env.step(action)
    
    print("\n3. Schema evolution step complete")
    print(f"   - Validation score: {obs.validity_score:.2f}")
    print(f"   - Best practices score: {obs.best_practices_score:.2f}")
    print(f"   - Contract pass rate: {obs.contract_test_report.contract_pass_rate:.2f}")
    print(f"   - Ticket satisfaction: {obs.ticket_satisfaction_score:.2f}")
    print(f"   - Reward: {obs.reward:.3f}")
    print(f"   - Breaking changes: {obs.breaking_change_report.breaking_change_count}")


def demo_environment_coexistence():
    """Demonstrate coexistence with APIEnvironment."""
    print("\n" + "=" * 80)
    print("Demo 2: Coexistence with APIEnvironment")
    print("=" * 80)
    
    # Create both environment types
    api_env = create_development_env(env_type="api")
    migration_env = create_development_env(env_type="migration")
    
    print("\n1. Both environments created successfully")
    print(f"   - API Environment: {type(api_env).__name__}")
    print(f"   - Migration Environment: {type(migration_env).__name__}")
    
    # Reset both
    api_obs = api_env.reset(seed=42)
    migration_obs = migration_env.reset(seed=42)
    
    print("\n2. Both environments reset independently")
    print(f"   - API episode ID: {api_obs.episode_info['episode_id']}")
    print(f"   - Migration episode ID: {migration_obs.episode_info['episode_id']}")
    
    print("\n3. Observation structure differences:")
    print(f"   - API has baseline_schema_json: {hasattr(api_obs, 'baseline_schema_json')}")
    print(f"   - Migration has baseline_schema_json: {hasattr(migration_obs, 'baseline_schema_json')}")
    print(f"   - API has contract_test_report: {hasattr(api_obs, 'contract_test_report')}")
    print(f"   - Migration has contract_test_report: {hasattr(migration_obs, 'contract_test_report')}")


def demo_configuration_flexibility():
    """Demonstrate configuration system flexibility."""
    print("\n" + "=" * 80)
    print("Demo 3: Configuration System Flexibility")
    print("=" * 80)
    
    # Create environments with different configurations
    dev_env = create_migration_env(environment="development")
    prod_env = create_migration_env(environment="production")
    
    print("\n1. Environments created with different configurations")
    print(f"   - Development environment: {type(dev_env).__name__}")
    print(f"   - Production environment: {type(prod_env).__name__}")
    
    # Reset both
    dev_obs = dev_env.reset(seed=42)
    prod_obs = prod_env.reset(seed=43)
    
    print("\n2. Both environments operational")
    print(f"   - Dev episode: {dev_obs.episode_info['episode_id'][:8]}...")
    print(f"   - Prod episode: {prod_obs.episode_info['episode_id'][:8]}...")


def demo_reward_components():
    """Demonstrate reward calculation with all components."""
    print("\n" + "=" * 80)
    print("Demo 4: Multi-Component Reward Calculation")
    print("=" * 80)
    
    env = create_migration_env()
    obs = env.reset(seed=42)
    
    # Submit evolved schema
    baseline = json.loads(obs.baseline_schema_json)
    evolved = baseline.copy()
    evolved["info"]["version"] = "1.1.0"
    
    action = MigrationAction(schema_json=json.dumps(evolved))
    obs = env.step(action)
    
    print("\n1. Reward components:")
    print(f"   - Contract preservation (45%): {obs.contract_test_report.contract_pass_rate:.3f}")
    print(f"   - Ticket satisfaction (25%): {obs.ticket_satisfaction_score:.3f}")
    print(f"   - Schema quality (20%):")
    print(f"     * Validity: {obs.validity_score:.3f}")
    print(f"     * Best practices: {obs.best_practices_score:.3f}")
    print(f"   - Progress delta (10%): {obs.episode_info.get('progress_delta', 0.0):.3f}")
    
    print("\n2. Penalties:")
    print(f"   - Breaking changes: {obs.breaking_change_report.breaking_penalty:.3f}")
    print(f"   - Behavior penalty: {obs.episode_info.get('penalty', 0.0):.3f}")
    
    print(f"\n3. Final reward: {obs.reward:.3f}")


def main():
    """Run all integration demos."""
    print("\n")
    print("*" * 80)
    print("MigrationEnvironment Integration Demonstration")
    print("*" * 80)
    
    try:
        demo_basic_integration()
        demo_environment_coexistence()
        demo_configuration_flexibility()
        demo_reward_components()
        
        print("\n" + "=" * 80)
        print("All integration demos completed successfully!")
        print("=" * 80)
        print("\nKey Integration Points Verified:")
        print("  - ValidationPipeline reuse for schema validation")
        print("  - MigrationRewardCalculator for multi-component rewards")
        print("  - Configuration system compatibility")
        print("  - Coexistence with APIEnvironment")
        print("  - Concurrent session support")
        
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
