# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""API Lifecycle Migration Environment Client."""

from typing import Any, Dict, List, Optional

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

try:
    from .migration_models import MigrationAction, MigrationObservation
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from migration_models import MigrationAction, MigrationObservation


class MigrationEnvClient(EnvClient[MigrationAction, MigrationObservation, Any]):
    """
    Client for the API Lifecycle Migration Environment.

    Connects to the migration environment server and handles serialization
    of MigrationAction / MigrationObservation types.

    Example:
        >>> with MigrationEnvClient(base_url="http://localhost:7860") as env:
        ...     result = env.reset()
        ...     obs = result.observation
        ...     print(obs.active_ticket.title)
        ...
        ...     action = MigrationAction(schema_json='{"openapi": "3.0.0", ...}', iteration=1)
        ...     result = env.step(action)
        ...     print(f"Reward: {result.reward}")
    """

    def _step_payload(self, action: MigrationAction) -> Dict:
        return {
            "schema_json": action.schema_json,
            "iteration": action.iteration,
            "migration_notes": getattr(action, "migration_notes", None),
        }

    def _parse_result(self, payload: Dict) -> StepResult[MigrationObservation]:
        obs_data = payload.get("observation", {})
        observation = self._parse_observation(obs_data)
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_observation(self, obs_data: Dict) -> MigrationObservation:
        from migration_models import (
            ContractTestResult,
            BreakingChangeReport,
            MigrationTicket,
        )
        try:
            from models import ValidationError
        except ImportError:
            from migration_models import BreakingChange as ValidationError

        # Parse validation errors
        validation_errors = []
        for e in obs_data.get("validation_errors", []):
            try:
                from models import ValidationError as VE
                validation_errors.append(VE(
                    error_type=e.get("error_type", ""),
                    severity=e.get("severity", "info"),
                    path=e.get("path", ""),
                    message=e.get("message", ""),
                    suggestion=e.get("suggestion", ""),
                ))
            except Exception:
                pass

        # Parse contract test report
        ctr_data = obs_data.get("contract_test_report", {})
        contract_test_report = ContractTestResult(
            contract_pass_rate=ctr_data.get("contract_pass_rate", 0.0),
            contract_failures=ctr_data.get("contract_failures", []),
            missing_operations=ctr_data.get("missing_operations", []),
            response_field_regressions=ctr_data.get("response_field_regressions", []),
            auth_regressions=ctr_data.get("auth_regressions", []),
        )

        # Parse breaking change report
        bcr_data = obs_data.get("breaking_change_report", {})
        breaking_change_report = BreakingChangeReport(
            breaking_change_count=bcr_data.get("breaking_change_count", 0),
            breaking_changes=bcr_data.get("breaking_changes", []),
            breaking_penalty=bcr_data.get("breaking_penalty", 0.0),
        )

        # Parse active ticket
        active_ticket = None
        ticket_data = obs_data.get("active_ticket")
        if ticket_data and isinstance(ticket_data, dict):
            try:
                active_ticket = MigrationTicket(**ticket_data)
            except Exception:
                pass

        return MigrationObservation(
            baseline_schema_json=obs_data.get("baseline_schema_json", "{}"),
            active_ticket=active_ticket,
            contract_test_report=contract_test_report,
            breaking_change_report=breaking_change_report,
            ticket_satisfaction_score=obs_data.get("ticket_satisfaction_score", 0.0),
            tickets_completed=obs_data.get("tickets_completed", 0),
            total_tickets=obs_data.get("total_tickets", 0),
            validation_errors=validation_errors,
            error_count=obs_data.get("error_count", 0),
            validity_score=obs_data.get("validity_score", 0.0),
            best_practices_score=obs_data.get("best_practices_score", 0.0),
            schema_feedback=obs_data.get("schema_feedback", ""),
            iteration=obs_data.get("iteration", 0),
            episode_info=obs_data.get("episode_info", {}),
            episode_done=obs_data.get("episode_done", False),
        )

    def _parse_state(self, payload: Dict) -> Any:
        return payload


# Keep old name as alias so any existing code doesn't break
APIEnvClient = MigrationEnvClient
