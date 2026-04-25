# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the API Lifecycle Migration Environment.

This module defines the migration-specific data structures that extend the base
API Conformance Gym models to support API evolution scenarios with backward
compatibility preservation.
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, validator, model_validator
from models import APIAction, APIObservation


class MigrationAction(APIAction):
    """Represents an agent's action for API migration - submitting an evolved schema.

    Extends APIAction with migration-specific fields for tracking evolution strategy.

    Attributes:
        schema_json: JSON-stringified evolved OpenAPI schema
        migration_notes: Optional agent notes about migration strategy
        iteration: Current iteration number for tracking
        metadata: Optional metadata (agent_id, timestamp, etc.)
    """

    migration_notes: Optional[str] = Field(
        default=None, description="Agent's migration strategy notes"
    )


class ContractExpectation(BaseModel):
    """Represents a single backward compatibility expectation.

    Attributes:
        path: API path (e.g., "/v1/orders")
        method: HTTP method (e.g., "get", "post")
        required_response_fields: List of required response fields
        required_security: Whether security is required for this operation
        status_code: Expected response status code
    """

    path: str = Field(..., min_length=1, description="API path")
    method: str = Field(
        ..., pattern="^(get|post|put|patch|delete)$", description="HTTP method"
    )
    required_response_fields: List[str] = Field(
        default_factory=list, description="Required response fields"
    )
    required_security: bool = Field(default=True, description="Security requirement")
    status_code: str = Field(default="200", description="Expected status code")


class ContractSuite(BaseModel):
    """Collection of backward compatibility requirements derived from baseline schema.

    Attributes:
        required_operations: List of (path, method) pairs that must be preserved
        required_security: Mapping of operation_id to security requirements
        required_response_fields: List of response field expectations
        baseline_schema_hash: Hash of baseline schema for validation
    """

    required_operations: List[Tuple[str, str]] = Field(
        ..., min_items=3, max_items=8, description="Required (path, method) operations"
    )
    required_security: Dict[str, bool] = Field(
        default_factory=dict, description="Operation security requirements"
    )
    required_response_fields: List[ContractExpectation] = Field(
        default_factory=list, description="Response field expectations"
    )
    baseline_schema_hash: str = Field(
        ..., min_length=1, description="Baseline schema hash"
    )


class ContractTestResult(BaseModel):
    """Results from running contract tests against an evolved schema.

    Attributes:
        contract_pass_rate: Percentage of contract expectations satisfied (0.0-1.0)
        contract_failures: Human-readable failure descriptions
        missing_operations: List of missing (path, method) operations
        response_field_regressions: List of missing response fields
        auth_regressions: List of operations with missing security
    """

    contract_pass_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Contract pass rate"
    )
    contract_failures: List[str] = Field(
        default_factory=list, description="Contract failure descriptions"
    )
    missing_operations: List[Tuple[str, str]] = Field(
        default_factory=list, description="Missing operations"
    )
    response_field_regressions: List[str] = Field(
        default_factory=list, description="Missing response fields"
    )
    auth_regressions: List[str] = Field(
        default_factory=list, description="Security regressions"
    )


class BreakingChange(BaseModel):
    """Represents a single breaking change between API versions.

    Attributes:
        change_type: Type of breaking change (e.g., "removed_operation", "removed_field")
        path: JSON path to the change location
        description: Human-readable description of the change
        severity: Severity level ("critical", "major", "minor")
    """

    change_type: str = Field(..., min_length=1, description="Type of breaking change")
    path: str = Field(..., min_length=1, description="JSON path to change")
    description: str = Field(..., min_length=1, description="Change description")
    severity: str = Field(
        ..., pattern="^(critical|major|minor)$", description="Change severity"
    )


class BreakingChangeReport(BaseModel):
    """Report of all breaking changes detected between schema versions.

    Attributes:
        breaking_change_count: Total number of breaking changes
        breaking_changes: List of detected breaking changes
        breaking_penalty: Calculated penalty for breaking changes
    """

    breaking_change_count: int = Field(
        ..., ge=0, description="Number of breaking changes"
    )
    breaking_changes: List[BreakingChange] = Field(
        default_factory=list, description="Detected breaking changes"
    )
    breaking_penalty: float = Field(..., ge=0.0, description="Breaking change penalty")

    @model_validator(mode="after")
    def validate_breaking_change_consistency(self):
        """Ensure breaking_change_count matches breaking_changes length."""
        if self.breaking_change_count != len(self.breaking_changes):
            raise ValueError(
                "breaking_change_count must equal length of breaking_changes"
            )
        return self


class MigrationTicket(BaseModel):
    """Represents a migration task with specific acceptance criteria.

    Attributes:
        ticket_id: Unique identifier for the ticket
        ticket_type: Type of migration task (additive, deprecation, security, compliance)
        title: Short descriptive title
        description: Detailed description of the task
        acceptance_criteria: List of criteria that must be satisfied
        difficulty: Task difficulty level (easy, medium, hard)
    """

    ticket_id: str = Field(..., min_length=1, description="Unique ticket identifier")
    ticket_type: str = Field(
        ...,
        pattern="^(additive|deprecation|security|compliance)$",
        description="Ticket type",
    )
    title: str = Field(..., min_length=1, description="Ticket title")
    description: str = Field(..., min_length=1, description="Ticket description")
    acceptance_criteria: List[str] = Field(
        ..., min_items=1, description="Acceptance criteria"
    )
    difficulty: str = Field(
        ..., pattern="^(easy|medium|hard)$", description="Difficulty level"
    )


class MigrationObservation(APIObservation):
    """Environment feedback for migration scenarios.

    Extends APIObservation with migration-specific fields for contract testing,
    breaking change detection, and ticket satisfaction tracking.

    Attributes:
        baseline_schema_json: Original v1 schema to maintain compatibility with
        active_ticket: Current migration ticket to satisfy
        contract_test_report: Results from contract compatibility testing
        breaking_change_report: Report of breaking changes detected
        ticket_satisfaction_score: Score for current ticket satisfaction (0.0-1.0)
        tickets_completed: Number of tickets completed so far
        total_tickets: Total number of tickets in the episode
    """

    baseline_schema_json: str = Field(
        ..., min_length=1, description="Baseline schema JSON"
    )
    active_ticket: Optional[MigrationTicket] = Field(
        default=None, description="Current active ticket"
    )
    contract_test_report: ContractTestResult = Field(
        ..., description="Contract test results"
    )
    breaking_change_report: BreakingChangeReport = Field(
        ..., description="Breaking change report"
    )
    ticket_satisfaction_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Ticket satisfaction score"
    )
    tickets_completed: int = Field(
        default=0, ge=0, description="Completed tickets count"
    )
    total_tickets: int = Field(default=0, ge=0, description="Total tickets count")

    @model_validator(mode="after")
    def validate_ticket_consistency(self):
        """Ensure tickets_completed doesn't exceed total_tickets."""
        if self.tickets_completed > self.total_tickets:
            raise ValueError("tickets_completed cannot exceed total_tickets")
        return self
