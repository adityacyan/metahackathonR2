#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Demo script for the API Lifecycle Migration Environment.

This script demonstrates how to use the MigrationEnvironment to evolve
API schemas while maintaining backward compatibility.
"""

import json
import sys
import os

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from server.migration_environment import MigrationEnvironment
from migration_models import MigrationAction


def print_observation_summary(observation, step_num):
    """Print a summary of the observation."""
    print(f"\n{'='*70}")
    print(f"Step {step_num} Summary")
    print(f"{'='*70}")
    
    print(f"\nActive Ticket: {observation.active_ticket.title if observation.active_ticket else 'None'}")
    print(f"Ticket Type: {observation.active_ticket.ticket_type if observation.active_ticket else 'N/A'}")
    
    print(f"\nContract Pass Rate: {observation.contract_test_report.contract_pass_rate:.1%}")
    print(f"Ticket Satisfaction: {observation.ticket_satisfaction_score:.1%}")
    print(f"Breaking Changes: {observation.breaking_change_report.breaking_change_count}")
    
    print(f"\nValidation:")
    print(f"  Validity Score: {observation.validity_score:.1%}")
    print(f"  Best Practices: {observation.best_practices_score:.1%}")
    print(f"  Errors: {observation.error_count}")
    
    print(f"\nProgress:")
    print(f"  Tickets Completed: {observation.tickets_completed}/{observation.total_tickets}")
    print(f"  Reward: {observation.reward:.3f}")
    
    if observation.contract_test_report.contract_failures:
        print(f"\nContract Failures:")
        for failure in observation.contract_test_report.contract_failures[:3]:
            print(f"  - {failure}")
    
    if observation.breaking_change_report.breaking_changes:
        print(f"\nBreaking Changes:")
        for change in observation.breaking_change_report.breaking_changes[:3]:
            print(f"  - {change.description}")
    
    print(f"\nFeedback: {observation.schema_feedback}")


def main():
    """Run the migration environment demo."""
    print("API Lifecycle Migration Environment Demo")
    print("="*70)
    
    # Initialize environment
    env = MigrationEnvironment()
    
    # Reset environment
    print("\nInitializing environment...")
    observation = env.reset(seed=42)
    
    print(f"\nBaseline Schema:")
    baseline_schema = json.loads(observation.baseline_schema_json)
    print(f"  Title: {baseline_schema['info']['title']}")
    print(f"  Version: {baseline_schema['info']['version']}")
    print(f"  Paths: {len(baseline_schema['paths'])}")
    
    print(f"\nContract Suite:")
    print(f"  Required Operations: {len(env._contract_suite.required_operations)}")
    print(f"  Required Response Fields: {len(env._contract_suite.required_response_fields)}")
    
    print(f"\nTicket Queue:")
    print(f"  Total Tickets: {observation.total_tickets}")
    print(f"  First Ticket: {observation.active_ticket.title}")
    
    # Step 1: Submit baseline schema (should maintain compatibility)
    print("\n" + "="*70)
    print("Step 1: Submit baseline schema (no changes)")
    print("="*70)
    
    action = MigrationAction(schema_json=observation.baseline_schema_json)
    observation = env.step(action)
    print_observation_summary(observation, 1)
    
    # Step 2: Add new endpoint for ticket satisfaction
    print("\n" + "="*70)
    print("Step 2: Add book reviews endpoint (satisfy ticket)")
    print("="*70)
    
    evolved_schema = json.loads(observation.baseline_schema_json)
    
    # Add reviews endpoint
    evolved_schema["paths"]["/v1/books/{id}/reviews"] = {
        "get": {
            "summary": "Get book reviews",
            "security": [{"apiKey": []}],
            "parameters": [
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "responses": {
                "200": {
                    "description": "List of reviews",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "reviews": {"type": "array"},
                                    "count": {"type": "integer"},
                                },
                            }
                        }
                    },
                }
            },
        },
        "post": {
            "summary": "Add a book review",
            "security": [{"apiKey": []}],
            "parameters": [
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "responses": {
                "201": {
                    "description": "Review created",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "review_id": {"type": "string"},
                                },
                            }
                        }
                    },
                }
            },
        },
    }
    
    action = MigrationAction(schema_json=json.dumps(evolved_schema))
    observation = env.step(action)
    print_observation_summary(observation, 2)
    
    # Step 3: Continue with more improvements
    print("\n" + "="*70)
    print("Step 3: Add descriptions for compliance")
    print("="*70)
    
    # Add descriptions to operations
    for path_name, path_item in evolved_schema["paths"].items():
        for method in ["get", "post", "put", "patch", "delete"]:
            if method in path_item:
                if "description" not in path_item[method]:
                    path_item[method]["description"] = f"Operation for {path_name}"
    
    action = MigrationAction(schema_json=json.dumps(evolved_schema))
    observation = env.step(action)
    print_observation_summary(observation, 3)
    
    # Final summary
    print("\n" + "="*70)
    print("Demo Complete")
    print("="*70)
    print(f"\nFinal Status:")
    print(f"  Episode Done: {observation.done}")
    print(f"  Tickets Completed: {observation.tickets_completed}/{observation.total_tickets}")
    print(f"  Final Contract Pass Rate: {observation.contract_test_report.contract_pass_rate:.1%}")
    print(f"  Total Breaking Changes: {observation.breaking_change_report.breaking_change_count}")
    
    if observation.done:
        print(f"\nTermination Reason: {observation.episode_info.get('termination_reason', 'unknown')}")


if __name__ == "__main__":
    main()
