#!/usr/bin/env python3
"""Debug script to check what the client receives from reset() and step()."""

import asyncio
import json
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from client import MigrationEnvClient
from migration_models import MigrationAction


async def debug_client():
    port = int(os.getenv("PORT", 7860))
    base_url = os.getenv("ENV_SERVER_URL", f"http://localhost:{port}")
    print(f"Connecting to {base_url}")

    try:
        client = MigrationEnvClient(base_url=base_url)

        print("\n1. Testing reset()...")
        reset_result = await client.reset()
        obs = reset_result.observation
        print(f"   active_ticket: {obs.active_ticket.title if obs.active_ticket else None}")
        print(f"   tickets: {obs.tickets_completed}/{obs.total_tickets}")
        print(f"   contract_pass_rate: {obs.contract_test_report.contract_pass_rate}")

        print("\n2. Testing step()...")
        baseline = json.loads(obs.baseline_schema_json)
        action = MigrationAction(schema_json=json.dumps(baseline), iteration=1)
        step_result = await client.step(action)
        print(f"   reward: {step_result.reward}")
        print(f"   done: {step_result.done}")
        print(f"   ticket_score: {step_result.observation.ticket_satisfaction_score}")

        await client.close()
        print("\nDone.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print(f"\nMake sure server is running: python start_server.py")


if __name__ == "__main__":
    asyncio.run(debug_client())
