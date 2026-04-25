# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
API Lifecycle Migration Environment Implementation.

This environment extends the API Conformance Gym to train RL agents on API evolution
scenarios. Agents must evolve v1 OpenAPI schemas while preserving backward compatibility,
managing breaking changes, and satisfying progressive migration tickets.

Performance optimizations:
- Efficient schema validation with early exits
- Cached contract suite generation
- Thread-safe concurrent episode execution
- Stable memory consumption across episodes
"""

import json
import logging
import random
import time
import threading
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

# Configure logging for error tracking
logger = logging.getLogger(__name__)

try:
    from ..migration_models import (
        MigrationAction,
        MigrationObservation,
        MigrationTicket,
        ContractTestResult,
        BreakingChangeReport,
        BreakingChange,
    )
    from .api_conformance_gym_environment import APIEnvironment
    from .validators import ValidationPipeline
    from .contract_grader import ContractSuiteGrader
    from .breaking_change_detector import BreakingChangeDetector
    from .ticket_grader import TicketSatisfactionGrader
    from .ticket_progression import TicketProgressionManager
    from .reward import MigrationRewardCalculator
except ImportError:
    import sys
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from migration_models import (
        MigrationAction,
        MigrationObservation,
        MigrationTicket,
        ContractTestResult,
        BreakingChangeReport,
        BreakingChange,
    )
    from server.api_conformance_gym_environment import APIEnvironment
    from server.validators import ValidationPipeline
    from server.contract_grader import ContractSuiteGrader
    from server.breaking_change_detector import BreakingChangeDetector
    from server.ticket_grader import TicketSatisfactionGrader
    from server.ticket_progression import TicketProgressionManager
    from server.reward import MigrationRewardCalculator


class MigrationEnvironment(APIEnvironment):
    """
    API Lifecycle Migration Environment.

    Extends APIEnvironment to support API evolution scenarios with backward
    compatibility preservation, breaking change detection, and progressive
    ticket-based migration tasks.

    Features:
    - Contract suite generation and testing for backward compatibility
    - Breaking change detection between schema versions
    - Progressive ticket-based evolution with satisfaction scoring
    - Multi-component reward calculation (contract 45%, ticket 25%, quality 20%, progress 10%)
    - Episode termination on ticket completion or max iterations
    - Thread-safe concurrent execution support
    - Optimized performance for large schemas
    """

    # Enable concurrent WebSocket sessions
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    # Environment configuration
    MAX_ITERATIONS = 15
    CONTRACT_COMPLETION_THRESHOLD = 0.95
    TICKET_SATISFACTION_THRESHOLD = 0.8

    # Thread-local storage for concurrent execution
    _thread_local = threading.local()

    # Baseline v1 schemas pool for migration scenarios
    BASELINE_SCHEMAS = [
        {
            "openapi": "3.0.0",
            "info": {"title": "Library API", "version": "1.0.0"},
            "paths": {
                "/v1/books": {
                    "get": {
                        "summary": "List all books",
                        "security": [{"apiKey": []}],
                        "responses": {
                            "200": {
                                "description": "List of books",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "books": {"type": "array"},
                                                "total": {"type": "integer"},
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    },
                    "post": {
                        "summary": "Create a book",
                        "security": [{"apiKey": []}],
                        "responses": {
                            "201": {
                                "description": "Book created",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "title": {"type": "string"},
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    },
                },
                "/v1/books/{id}": {
                    "get": {
                        "summary": "Get book by ID",
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
                                "description": "Book details",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "title": {"type": "string"},
                                                "author": {"type": "string"},
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    }
                },
                "/v1/authors": {
                    "get": {
                        "summary": "List all authors",
                        "security": [{"apiKey": []}],
                        "responses": {
                            "200": {
                                "description": "List of authors",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "authors": {"type": "array"},
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    }
                },
            },
            "components": {
                "securitySchemes": {
                    "apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
                }
            },
        },
    ]

    def __init__(self, **kwargs):
        """Initialize the Migration Environment.

        Thread-safe initialization for concurrent episode execution.

        Args:
            **kwargs: Additional arguments passed to parent APIEnvironment
        """
        super().__init__(**kwargs)

        # Migration-specific components (thread-safe instances)
        self._contract_grader = ContractSuiteGrader()
        self._breaking_change_detector = BreakingChangeDetector()
        self._ticket_grader = TicketSatisfactionGrader()

        # Lock for thread-safe operations (if needed for shared state)
        self._lock = threading.Lock()

        # Episode state (instance-specific, naturally thread-safe)
        self._baseline_schema: Optional[Dict[str, Any]] = None
        self._contract_suite = None
        self._ticket_progression: Optional[TicketProgressionManager] = None
        self._previous_schema: Optional[Dict[str, Any]] = None
        self._previous_contract_rate: float = 0.0
        self._previous_ticket_score: float = 0.0

    def reset(self, seed: Optional[int] = None) -> MigrationObservation:
        """
        Reset the environment with a new baseline schema and ticket queue.

        Args:
            seed: Optional seed for deterministic baseline selection

        Returns:
            MigrationObservation with initial state and baseline schema
        """
        start_time = time.time()

        # Set seed for deterministic behavior
        if seed is not None:
            random.seed(seed)

        # Generate new episode ID and reset step count
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count += 1

        # Select baseline v1 schema
        self._baseline_schema = random.choice(self.BASELINE_SCHEMAS).copy()

        # Generate contract suite from baseline
        try:
            self._contract_suite = self._contract_grader.generate_contract_suite(
                self._baseline_schema
            )
        except ValueError as e:
            logger.error(
                f"Contract suite generation failed for baseline schema: {e}",
                exc_info=True,
                extra={
                    "episode_id": self._state.episode_id,
                    "baseline_schema": self._baseline_schema,
                },
            )
            raise RuntimeError(
                f"Failed to generate contract suite: {e}. "
                f"Baseline schema must contain at least 3 operations."
            )

        # Generate ticket queue
        try:
            ticket_queue = self._generate_ticket_queue()
            self._ticket_progression = TicketProgressionManager(ticket_queue)
        except Exception as e:
            logger.error(
                f"Ticket queue generation failed: {e}",
                exc_info=True,
                extra={"episode_id": self._state.episode_id},
            )
            # Provide fallback with empty ticket queue
            self._ticket_progression = TicketProgressionManager([])
            logger.warning("Using empty ticket queue as fallback")

        # Initialize episode state
        self._previous_schema = self._baseline_schema.copy()
        self._previous_contract_rate = 1.0
        self._previous_ticket_score = 0.0

        # Initialize parent state
        self._current_state = None

        # Create initial contract test report
        initial_contract_report = ContractTestResult(
            contract_pass_rate=1.0,
            contract_failures=[],
            missing_operations=[],
            response_field_regressions=[],
            auth_regressions=[],
        )

        # Create initial breaking change report
        initial_breaking_report = BreakingChangeReport(
            breaking_change_count=0, breaking_changes=[], breaking_penalty=0.0
        )

        # Create initial observation
        observation = MigrationObservation(
            baseline_schema_json=json.dumps(self._baseline_schema),
            active_ticket=self._ticket_progression.get_active_ticket(),
            contract_test_report=initial_contract_report,
            breaking_change_report=initial_breaking_report,
            ticket_satisfaction_score=0.0,
            tickets_completed=self._ticket_progression.tickets_completed,
            total_tickets=self._ticket_progression.total_tickets,
            validation_errors=[],
            error_count=0,
            validity_score=0.0,
            best_practices_score=0.0,
            schema_feedback="New migration episode started. Evolve the baseline schema to satisfy the active ticket while maintaining backward compatibility.",
            iteration=0,
            episode_info={
                "episode_id": self._state.episode_id,
                "step_count": 0,
                "iteration_count": 0,
                "max_iterations": self.MAX_ITERATIONS,
                "task_name": "API Lifecycle Migration",
            },
            episode_done=False,
        )

        # Ensure reset completes within 100ms
        elapsed = (time.time() - start_time) * 1000
        if elapsed > 100:
            print(f"Warning: reset() took {elapsed:.1f}ms (target: <100ms)")

        return observation

    @property
    def state(self) -> State:
        """
        Return the current OpenEnv state metadata.

        The UI and HTTP/WebSocket clients may call state immediately after reset.
        MigrationEnvironment does not rely on APIEnvironment._current_state, so we
        expose the canonical OpenEnv State object to keep reset/state flows stable.
        """
        return self._state

    def step(self, action: MigrationAction) -> MigrationObservation:
        """
        Execute a migration step by validating evolved schema and calculating reward.

        Args:
            action: MigrationAction containing evolved schema JSON

        Returns:
            MigrationObservation with reward and done fields populated
        """
        start_time = time.time()

        if self._baseline_schema is None or self._contract_suite is None:
            error_msg = "Environment not initialized. Call reset() first."
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Increment step count
        self._state.step_count += 1
        iteration_count = self._state.step_count

        # Parse evolved schema with detailed error handling
        try:
            current_schema = json.loads(action.schema_json)
        except json.JSONDecodeError as e:
            logger.warning(
                f"Invalid JSON schema submitted at iteration {iteration_count}: {e}",
                extra={
                    "episode_id": self._state.episode_id,
                    "iteration": iteration_count,
                },
            )
            return self._create_error_observation(
                f"Invalid JSON schema: {str(e)}", iteration_count
            )
        except Exception as e:
            logger.error(
                f"Unexpected error parsing schema at iteration {iteration_count}: {e}",
                exc_info=True,
                extra={
                    "episode_id": self._state.episode_id,
                    "iteration": iteration_count,
                },
            )
            return self._create_error_observation(
                f"Schema parsing error: {str(e)}", iteration_count
            )

        # Wrap all processing in try-except to maintain environment stability
        try:
            # Step 1: Validate evolved schema
            validation_result = self._validation_pipeline.validate(action.schema_json)

            # Step 2: Run contract tests with error handling
            try:
                contract_result = self._contract_grader.run_contract_tests(
                    current_schema, self._contract_suite
                )
            except Exception as e:
                logger.error(
                    f"Contract testing failed at iteration {iteration_count}: {e}",
                    exc_info=True,
                    extra={
                        "episode_id": self._state.episode_id,
                        "iteration": iteration_count,
                    },
                )
                # Provide fallback contract result
                contract_result = ContractTestResult(
                    contract_pass_rate=0.0,
                    contract_failures=[f"Contract testing error: {str(e)}"],
                    missing_operations=[],
                    response_field_regressions=[],
                    auth_regressions=[],
                )

            # Step 3: Detect breaking changes with error handling
            try:
                breaking_report = (
                    self._breaking_change_detector.detect_breaking_changes(
                        self._previous_schema, current_schema
                    )
                )
            except Exception as e:
                logger.error(
                    f"Breaking change detection failed at iteration {iteration_count}: {e}",
                    exc_info=True,
                    extra={
                        "episode_id": self._state.episode_id,
                        "iteration": iteration_count,
                    },
                )
                # Provide fallback breaking change report
                breaking_report = BreakingChangeReport(
                    breaking_change_count=0, breaking_changes=[], breaking_penalty=0.0
                )

            # Step 4: Score ticket satisfaction with error handling
            active_ticket = self._ticket_progression.get_active_ticket()
            if active_ticket:
                try:
                    ticket_score = self._ticket_grader.score_ticket_satisfaction(
                        current_schema, active_ticket
                    )
                except Exception as e:
                    logger.error(
                        f"Ticket grading failed at iteration {iteration_count}: {e}",
                        exc_info=True,
                        extra={
                            "episode_id": self._state.episode_id,
                            "iteration": iteration_count,
                            "ticket_id": active_ticket.ticket_id,
                        },
                    )
                    # Provide fallback score
                    ticket_score = 0.0
            else:
                ticket_score = 1.0

            # Step 5: Calculate progress delta
            previous_combined = (
                self._previous_contract_rate + self._previous_ticket_score
            ) / 2
            current_combined = (contract_result.contract_pass_rate + ticket_score) / 2
            progress_delta = max(0.0, current_combined - previous_combined)

            # Step 6: Calculate behavior penalties
            penalty = self._calculate_behavior_penalties(
                action, current_schema, iteration_count, progress_delta
            )

            # Step 7: Calculate shaped reward using MigrationRewardCalculator
            reward = MigrationRewardCalculator.calculate_reward(
                contract_pass_rate=contract_result.contract_pass_rate,
                ticket_score=ticket_score,
                validity_score=validation_result.validity_score,
                best_practices_score=validation_result.best_practices_score,
                progress_delta=progress_delta,
                breaking_penalty=breaking_report.breaking_penalty,
                behavior_penalty=penalty,
            )

            # Step 8: Update state
            self._previous_schema = current_schema
            self._previous_contract_rate = contract_result.contract_pass_rate
            self._previous_ticket_score = ticket_score

            # Step 9: Check ticket completion and advance
            ticket_advanced = self._ticket_progression.check_and_advance(ticket_score)

            # Step 10: Check termination conditions
            all_tickets_done = (
                self._ticket_progression.is_all_tickets_completed()
                and contract_result.contract_pass_rate
                >= self.CONTRACT_COMPLETION_THRESHOLD
            )
            max_iterations_reached = iteration_count >= self.MAX_ITERATIONS
            episode_done = all_tickets_done or max_iterations_reached

            # Step 11: Create comprehensive observation
            observation = self._create_observation(
                validation_result=validation_result,
                contract_result=contract_result,
                breaking_report=breaking_report,
                ticket_score=ticket_score,
                reward=reward,
                iteration_count=iteration_count,
                episode_done=episode_done,
                ticket_advanced=ticket_advanced,
                progress_delta=progress_delta,
                penalty=penalty,
            )

            # Ensure step completes within 500ms
            elapsed = (time.time() - start_time) * 1000
            if elapsed > 500:
                logger.warning(
                    f"step() took {elapsed:.1f}ms (target: <500ms)",
                    extra={
                        "episode_id": self._state.episode_id,
                        "iteration": iteration_count,
                    },
                )

            return observation

        except Exception as e:
            # Catch-all for unexpected errors to maintain environment stability
            logger.error(
                f"Unexpected error in step() at iteration {iteration_count}: {e}",
                exc_info=True,
                extra={
                    "episode_id": self._state.episode_id,
                    "iteration": iteration_count,
                },
            )
            return self._create_error_observation(
                f"Internal environment error: {str(e)}", iteration_count
            )

    def _generate_ticket_queue(self) -> List[MigrationTicket]:
        """Generate a queue of migration tickets for the episode.

        Returns:
            List of MigrationTicket objects
        """
        tickets = [
            MigrationTicket(
                ticket_id="T001",
                ticket_type="additive",
                title="Add book reviews endpoint",
                description="Add a new endpoint for book reviews to enhance user engagement",
                acceptance_criteria=[
                    "Add path /v1/books/{id}/reviews with GET method",
                    "Add path /v1/books/{id}/reviews with POST method",
                    "Response field 'reviews' must be present in GET response",
                ],
                difficulty="easy",
            ),
            MigrationTicket(
                ticket_id="T002",
                ticket_type="security",
                title="Enhance API security",
                description="Ensure all endpoints have proper authentication",
                acceptance_criteria=[
                    "All endpoints must have security requirements",
                    "Security scheme must be defined in components",
                ],
                difficulty="medium",
            ),
            MigrationTicket(
                ticket_id="T003",
                ticket_type="compliance",
                title="Improve API documentation",
                description="Add comprehensive descriptions and examples",
                acceptance_criteria=[
                    "All operations must have descriptions",
                    "Response schemas must be defined",
                ],
                difficulty="medium",
            ),
        ]

        return tickets

    def _calculate_behavior_penalties(
        self,
        action: MigrationAction,
        current_schema: Dict[str, Any],
        iteration: int,
        progress_delta: float,
    ) -> float:
        """Calculate penalties for undesirable agent behavior.

        Args:
            action: Current action
            current_schema: Current schema
            iteration: Current iteration number
            progress_delta: Progress improvement

        Returns:
            Total penalty value
        """
        penalty = 0.0

        # Penalize repeated schema submissions
        if self._previous_schema and current_schema == self._previous_schema:
            penalty += 0.10

        # Penalize no progress after iteration 2
        if iteration > 2 and progress_delta < 0.01:
            penalty += 0.05

        return penalty

    def _generate_migration_feedback(
        self,
        validation_result,
        contract_result: ContractTestResult,
        ticket_score: float,
        breaking_report: BreakingChangeReport,
    ) -> str:
        """Generate human-readable feedback for migration progress.

        Args:
            validation_result: Validation result
            contract_result: Contract test result
            ticket_score: Ticket satisfaction score
            breaking_report: Breaking change report

        Returns:
            Human-readable feedback string
        """
        feedback_parts = []

        # Contract feedback
        if contract_result.contract_pass_rate >= 0.95:
            feedback_parts.append("Excellent backward compatibility maintained!")
        elif contract_result.contract_pass_rate >= 0.7:
            feedback_parts.append(
                f"Good progress on compatibility ({contract_result.contract_pass_rate:.1%})"
            )
        else:
            feedback_parts.append(
                f"Contract violations detected ({len(contract_result.contract_failures)} issues)"
            )

        # Ticket feedback
        if ticket_score >= self.TICKET_SATISFACTION_THRESHOLD:
            feedback_parts.append("Ticket requirements satisfied!")
        else:
            feedback_parts.append(
                f"Ticket progress: {ticket_score:.1%} (need {self.TICKET_SATISFACTION_THRESHOLD:.0%})"
            )

        # Breaking change feedback
        if breaking_report.breaking_change_count > 0:
            feedback_parts.append(
                f"Warning: {breaking_report.breaking_change_count} breaking changes detected"
            )

        # Validation feedback
        if validation_result.validity_score < 0.7:
            feedback_parts.append("Schema validation issues need attention")

        return " ".join(feedback_parts)

    def _create_observation(
        self,
        validation_result,
        contract_result: ContractTestResult,
        breaking_report: BreakingChangeReport,
        ticket_score: float,
        reward: float,
        iteration_count: int,
        episode_done: bool,
        ticket_advanced: bool,
        progress_delta: float,
        penalty: float,
    ) -> MigrationObservation:
        """Create a comprehensive observation with all required components.

        This method centralizes observation generation to ensure all required fields
        are consistently populated according to Requirements 7.1-7.5.

        Args:
            validation_result: Schema validation result
            contract_result: Contract test result
            breaking_report: Breaking change report
            ticket_score: Ticket satisfaction score
            reward: Calculated reward value
            iteration_count: Current iteration number
            episode_done: Whether episode is complete
            ticket_advanced: Whether ticket was advanced
            progress_delta: Progress improvement
            penalty: Behavior penalty

        Returns:
            MigrationObservation with all required components
        """
        # Get ticket completion status
        tickets_completed, total_tickets = (
            self._ticket_progression.get_completion_status()
        )

        # Generate human-readable feedback
        schema_feedback = self._generate_migration_feedback(
            validation_result, contract_result, ticket_score, breaking_report
        )

        # Create comprehensive episode info
        all_tickets_done = (
            self._ticket_progression.is_all_tickets_completed()
            and contract_result.contract_pass_rate >= self.CONTRACT_COMPLETION_THRESHOLD
        )

        episode_info = {
            "episode_id": self._state.episode_id,
            "step_count": self._state.step_count,
            "iteration_count": iteration_count,
            "max_iterations": self.MAX_ITERATIONS,
            "task_name": "API Lifecycle Migration",
            "contract_pass_rate": contract_result.contract_pass_rate,
            "ticket_satisfaction_score": ticket_score,
            "breaking_change_count": breaking_report.breaking_change_count,
            "progress_delta": progress_delta,
            "penalty": penalty,
            "ticket_advanced": ticket_advanced,
        }

        if episode_done:
            episode_info.update(
                {
                    "termination_reason": (
                        "all_tickets_completed"
                        if all_tickets_done
                        else "max_iterations"
                    ),
                    "final_contract_pass_rate": contract_result.contract_pass_rate,
                    "final_ticket_score": ticket_score,
                    "tickets_completed": tickets_completed,
                    "total_tickets": total_tickets,
                }
            )

        # Create observation with all required components (Requirement 7.1-7.5)
        observation = MigrationObservation(
            # Requirement 7.1: baseline schema, active ticket, contract results
            baseline_schema_json=json.dumps(self._baseline_schema),
            active_ticket=self._ticket_progression.get_active_ticket(),
            contract_test_report=contract_result,
            # Requirement 7.2: breaking change reports with detailed descriptions
            breaking_change_report=breaking_report,
            # Requirement 7.3: ticket satisfaction scores and completion progress
            ticket_satisfaction_score=ticket_score,
            tickets_completed=tickets_completed,
            total_tickets=total_tickets,
            # Requirement 7.4: validation errors and quality scores
            validation_errors=validation_result.errors,
            error_count=len(validation_result.errors),
            validity_score=validation_result.validity_score,
            best_practices_score=validation_result.best_practices_score,
            # Requirement 7.5: current reward and termination status
            schema_feedback=schema_feedback,
            iteration=iteration_count,
            episode_info=episode_info,
            episode_done=episode_done,
        )

        observation.reward = reward
        observation.done = episode_done

        return observation

    def _create_error_observation(
        self, error_message: str, iteration: int
    ) -> MigrationObservation:
        """Create an error observation for invalid inputs.

        Handles invalid JSON schemas and other errors gracefully by returning
        descriptive error observations without crashing (Requirement 10.1, 10.5).

        Args:
            error_message: Error description
            iteration: Current iteration

        Returns:
            MigrationObservation with error information and zero reward
        """
        from models import ValidationError as VError

        logger.info(
            f"Creating error observation: {error_message}",
            extra={"episode_id": self._state.episode_id, "iteration": iteration},
        )

        # Create error contract report
        error_contract_report = ContractTestResult(
            contract_pass_rate=0.0,
            contract_failures=[error_message],
            missing_operations=[],
            response_field_regressions=[],
            auth_regressions=[],
        )

        # Create empty breaking change report
        error_breaking_report = BreakingChangeReport(
            breaking_change_count=0, breaking_changes=[], breaking_penalty=0.0
        )

        # Get ticket completion status safely
        try:
            tickets_completed, total_tickets = (
                self._ticket_progression.get_completion_status()
            )
            active_ticket = self._ticket_progression.get_active_ticket()
        except Exception as e:
            logger.error(
                f"Failed to get ticket status in error observation: {e}", exc_info=True
            )
            tickets_completed, total_tickets = 0, 0
            active_ticket = None

        # Create validation error to match error_count
        validation_errors = [
            VError(
                error_type=(
                    "json_parse_error" if "JSON" in error_message else "schema_error"
                ),
                severity="critical",
                path="schema",
                message=error_message,
                suggestion=(
                    "Please provide valid JSON schema"
                    if "JSON" in error_message
                    else "Please fix the schema error"
                ),
            )
        ]

        # Create comprehensive error observation
        observation = MigrationObservation(
            baseline_schema_json=json.dumps(self._baseline_schema),
            active_ticket=active_ticket,
            contract_test_report=error_contract_report,
            breaking_change_report=error_breaking_report,
            ticket_satisfaction_score=0.0,
            tickets_completed=tickets_completed,
            total_tickets=total_tickets,
            validation_errors=validation_errors,
            error_count=1,
            validity_score=0.0,
            best_practices_score=0.0,
            schema_feedback=error_message,
            iteration=iteration,
            episode_info={
                "episode_id": self._state.episode_id,
                "step_count": self._state.step_count,
                "error": error_message,
                "error_type": "schema_error",
            },
            episode_done=False,
        )

        observation.reward = 0.0
        observation.done = False

        return observation
