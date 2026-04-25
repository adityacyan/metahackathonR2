#!/usr/bin/env python3
"""Quick test to verify all imports and basic functionality work."""

import json
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


def test_imports():
    print("Testing imports...")

    try:
        from migration_models import MigrationAction, MigrationObservation, MigrationTicket
        print("  migration_models OK")
    except Exception as e:
        print(f"  migration_models FAILED: {e}")
        return False

    try:
        from server.migration_environment import MigrationEnvironment
        from server.validators import ValidationPipeline
        from server.reward import MigrationRewardCalculator
        from server.contract_grader import ContractSuiteGrader
        from server.breaking_change_detector import BreakingChangeDetector
        from server.ticket_grader import TicketSatisfactionGrader
        print("  server components OK")
    except Exception as e:
        print(f"  server components FAILED: {e}")
        return False

    try:
        from client import MigrationEnvClient
        print("  client OK")
    except Exception as e:
        print(f"  client FAILED: {e}")
        return False

    try:
        from server.app import app
        print("  server.app OK")
    except Exception as e:
        print(f"  server.app FAILED: {e}")
        return False

    return True


def test_basic_functionality():
    print("\nTesting basic functionality...")

    try:
        from server.migration_environment import MigrationEnvironment
        from migration_models import MigrationAction

        env = MigrationEnvironment()
        obs = env.reset()
        print(f"  reset OK — ticket: {obs.active_ticket.title if obs.active_ticket else None}")

        action = MigrationAction(schema_json=obs.baseline_schema_json, iteration=1)
        obs2 = env.step(action)
        print(f"  step OK — reward: {obs2.reward:.3f}, contract: {obs2.contract_test_report.contract_pass_rate:.2f}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("API Lifecycle Migration — Quick Test")
    print("=" * 40)

    if not test_imports():
        print("\nImport tests FAILED")
        return 1

    if not test_basic_functionality():
        print("\nFunctionality tests FAILED")
        return 1

    print("\nAll tests passed!")
    print("\nStart server: python start_server.py")
    print("Run inference: python inference.py")
    return 0


if __name__ == "__main__":
    exit(main())
