# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Ticket Satisfaction Grader for API Lifecycle Migration Environment.

This module implements ticket satisfaction scoring to evaluate schema changes
against migration ticket acceptance criteria. It supports different ticket types
with specific evaluation logic for each type.
"""

from typing import Any, Dict, List, Set

try:
    from ..migration_models import MigrationTicket
except ImportError:
    import sys
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from migration_models import MigrationTicket


class TicketSatisfactionGrader:
    """Evaluates schema changes against migration ticket acceptance criteria."""

    VALID_HTTP_METHODS = ["get", "post", "put", "patch", "delete"]
    SATISFACTION_THRESHOLD = 0.8

    def score_ticket_satisfaction(
        self, current_schema: Dict[str, Any], ticket: MigrationTicket
    ) -> float:
        """Evaluate schema changes against ticket acceptance criteria.

        Scores how well the current schema satisfies the ticket's acceptance
        criteria. Different ticket types use specialized evaluation logic.

        Args:
            current_schema: Current evolved OpenAPI schema dictionary
            ticket: Migration ticket with acceptance criteria

        Returns:
            Satisfaction score in range [0.0, 1.0]
        """
        if ticket.ticket_type == "additive":
            return self._score_additive_ticket(current_schema, ticket)
        elif ticket.ticket_type == "deprecation":
            return self._score_deprecation_ticket(current_schema, ticket)
        elif ticket.ticket_type == "security":
            return self._score_security_ticket(current_schema, ticket)
        elif ticket.ticket_type == "compliance":
            return self._score_compliance_ticket(current_schema, ticket)
        else:
            return 0.0

    def _score_additive_ticket(
        self, schema: Dict[str, Any], ticket: MigrationTicket
    ) -> float:
        """Score additive ticket satisfaction.

        Additive tickets require new endpoints or fields to be added.
        Criteria typically specify paths, methods, or response fields to add.

        Args:
            schema: Current schema
            ticket: Additive ticket

        Returns:
            Satisfaction score [0.0, 1.0]
        """
        satisfied_criteria = 0
        total_criteria = len(ticket.acceptance_criteria)

        if total_criteria == 0:
            return 0.0

        paths = schema.get("paths", {})

        for criterion in ticket.acceptance_criteria:
            criterion_lower = criterion.lower()

            # Check for new path additions
            if "add path" in criterion_lower or "new endpoint" in criterion_lower:
                # Extract path from criterion (e.g., "Add path /v1/reviews")
                path_to_check = self._extract_path_from_criterion(criterion)
                if path_to_check and path_to_check in paths:
                    satisfied_criteria += 1
                    continue

            # Check for new operation additions
            if "add" in criterion_lower and any(
                method in criterion_lower for method in self.VALID_HTTP_METHODS
            ):
                # Extract path and method (e.g., "Add GET /v1/books/{id}/reviews")
                path, method = self._extract_operation_from_criterion(criterion)
                if path and method:
                    path_item = paths.get(path, {})
                    if isinstance(path_item, dict) and method in path_item:
                        satisfied_criteria += 1
                        continue

            # Check for response field additions
            if "response field" in criterion_lower or "add field" in criterion_lower:
                # Extract field name from criterion
                field_name = self._extract_field_from_criterion(criterion)
                if field_name and self._schema_has_response_field(schema, field_name):
                    satisfied_criteria += 1
                    continue

            # Check for general schema expansion (operation count increase)
            if "expand" in criterion_lower or "increase" in criterion_lower:
                operation_count = self._count_operations(schema)
                if operation_count >= 5:  # Reasonable expansion threshold
                    satisfied_criteria += 1
                    continue

        return satisfied_criteria / total_criteria

    def _score_deprecation_ticket(
        self, schema: Dict[str, Any], ticket: MigrationTicket
    ) -> float:
        """Score deprecation ticket satisfaction.

        Deprecation tickets require marking endpoints or fields as deprecated
        while maintaining backward compatibility.

        Args:
            schema: Current schema
            ticket: Deprecation ticket

        Returns:
            Satisfaction score [0.0, 1.0]
        """
        satisfied_criteria = 0
        total_criteria = len(ticket.acceptance_criteria)

        if total_criteria == 0:
            return 0.0

        paths = schema.get("paths", {})

        for criterion in ticket.acceptance_criteria:
            criterion_lower = criterion.lower()

            # Check for deprecated flag on operations
            if "deprecate" in criterion_lower or "mark as deprecated" in criterion_lower:
                path, method = self._extract_operation_from_criterion(criterion)
                if path and method:
                    path_item = paths.get(path, {})
                    if isinstance(path_item, dict) and method in path_item:
                        operation = path_item[method]
                        if isinstance(operation, dict) and operation.get("deprecated", False):
                            satisfied_criteria += 1
                            continue

            # Check for v2 alternative endpoints
            if "v2" in criterion_lower or "alternative" in criterion_lower:
                v2_paths = [p for p in paths.keys() if "/v2/" in p]
                if v2_paths:
                    satisfied_criteria += 1
                    continue

            # Check for deprecation notices in descriptions
            if "description" in criterion_lower or "notice" in criterion_lower:
                has_deprecation_notice = self._has_deprecation_notices(schema)
                if has_deprecation_notice:
                    satisfied_criteria += 1
                    continue

        return satisfied_criteria / total_criteria

    def _score_security_ticket(
        self, schema: Dict[str, Any], ticket: MigrationTicket
    ) -> float:
        """Score security ticket satisfaction.

        Security tickets require adding authentication, authorization, or
        security schemes to operations.

        Args:
            schema: Current schema
            ticket: Security ticket

        Returns:
            Satisfaction score [0.0, 1.0]
        """
        satisfied_criteria = 0
        total_criteria = len(ticket.acceptance_criteria)

        if total_criteria == 0:
            return 0.0

        paths = schema.get("paths", {})
        components = schema.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        global_security = schema.get("security", [])

        for criterion in ticket.acceptance_criteria:
            criterion_lower = criterion.lower()

            # Check for security scheme definitions
            if "security scheme" in criterion_lower or "add authentication" in criterion_lower:
                if security_schemes:
                    satisfied_criteria += 1
                    continue

            # Check for operation-level security
            if "protect" in criterion_lower or "secure" in criterion_lower:
                path, method = self._extract_operation_from_criterion(criterion)
                if path and method:
                    path_item = paths.get(path, {})
                    if isinstance(path_item, dict) and method in path_item:
                        operation = path_item[method]
                        if isinstance(operation, dict):
                            operation_security = operation.get("security")
                            if operation_security is not None or global_security:
                                satisfied_criteria += 1
                                continue

            # Check for global security coverage
            if "all endpoints" in criterion_lower or "global security" in criterion_lower:
                if global_security or self._all_operations_secured(schema):
                    satisfied_criteria += 1
                    continue

            # Check for specific security types (API key, OAuth, etc.)
            if any(
                sec_type in criterion_lower
                for sec_type in ["api key", "oauth", "bearer", "jwt"]
            ):
                if self._has_security_type(security_schemes, criterion_lower):
                    satisfied_criteria += 1
                    continue

        return satisfied_criteria / total_criteria

    def _score_compliance_ticket(
        self, schema: Dict[str, Any], ticket: MigrationTicket
    ) -> float:
        """Score compliance ticket satisfaction.

        Compliance tickets require schema to meet specific standards or
        regulatory requirements (e.g., GDPR, OpenAPI best practices).

        Args:
            schema: Current schema
            ticket: Compliance ticket

        Returns:
            Satisfaction score [0.0, 1.0]
        """
        satisfied_criteria = 0
        total_criteria = len(ticket.acceptance_criteria)

        if total_criteria == 0:
            return 0.0

        for criterion in ticket.acceptance_criteria:
            criterion_lower = criterion.lower()

            # Check for required metadata fields
            if "info" in criterion_lower or "metadata" in criterion_lower:
                info = schema.get("info", {})
                if isinstance(info, dict) and info.get("title") and info.get("version"):
                    satisfied_criteria += 1
                    continue

            # Check for operation descriptions
            if "description" in criterion_lower or "documentation" in criterion_lower:
                if self._has_operation_descriptions(schema):
                    satisfied_criteria += 1
                    continue

            # Check for response schemas
            if "response schema" in criterion_lower or "response definition" in criterion_lower:
                if self._has_response_schemas(schema):
                    satisfied_criteria += 1
                    continue

            # Check for error responses
            if "error" in criterion_lower or "4xx" in criterion_lower or "5xx" in criterion_lower:
                if self._has_error_responses(schema):
                    satisfied_criteria += 1
                    continue

            # Check for examples
            if "example" in criterion_lower:
                if self._has_examples(schema):
                    satisfied_criteria += 1
                    continue

        return satisfied_criteria / total_criteria

    def _extract_path_from_criterion(self, criterion: str) -> str:
        """Extract API path from acceptance criterion text.

        Args:
            criterion: Acceptance criterion text

        Returns:
            Extracted path or empty string
        """
        words = criterion.split()
        for word in words:
            if word.startswith("/"):
                return word.rstrip(".,;:")
        return ""

    def _extract_operation_from_criterion(self, criterion: str) -> tuple:
        """Extract path and method from acceptance criterion text.

        Args:
            criterion: Acceptance criterion text

        Returns:
            Tuple of (path, method) or (None, None)
        """
        criterion_lower = criterion.lower()
        path = self._extract_path_from_criterion(criterion)

        for method in self.VALID_HTTP_METHODS:
            if method in criterion_lower:
                return (path, method)

        return (None, None)

    def _extract_field_from_criterion(self, criterion: str) -> str:
        """Extract field name from acceptance criterion text.

        Args:
            criterion: Acceptance criterion text

        Returns:
            Extracted field name or empty string
        """
        words = criterion.split()
        for i, word in enumerate(words):
            if word.lower() in ["field", "property", "attribute"] and i + 1 < len(words):
                return words[i + 1].strip("'\".,;:")
        return ""

    def _count_operations(self, schema: Dict[str, Any]) -> int:
        """Count total operations in schema.

        Args:
            schema: OpenAPI schema

        Returns:
            Total operation count
        """
        count = 0
        paths = schema.get("paths", {})

        for path_item in paths.values():
            if isinstance(path_item, dict):
                for method in self.VALID_HTTP_METHODS:
                    if method in path_item:
                        count += 1

        return count

    def _schema_has_response_field(self, schema: Dict[str, Any], field_name: str) -> bool:
        """Check if any operation response contains the specified field.

        Args:
            schema: OpenAPI schema
            field_name: Field name to search for

        Returns:
            True if field exists in any response
        """
        paths = schema.get("paths", {})

        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue

            for method in self.VALID_HTTP_METHODS:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                responses = operation.get("responses", {})
                for response in responses.values():
                    if not isinstance(response, dict):
                        continue

                    content = response.get("content", {})
                    for media_type in content.values():
                        if not isinstance(media_type, dict):
                            continue

                        schema_obj = media_type.get("schema", {})
                        if isinstance(schema_obj, dict):
                            properties = schema_obj.get("properties", {})
                            if field_name in properties:
                                return True

        return False

    def _has_deprecation_notices(self, schema: Dict[str, Any]) -> bool:
        """Check if schema contains deprecation notices.

        Args:
            schema: OpenAPI schema

        Returns:
            True if deprecation notices found
        """
        paths = schema.get("paths", {})

        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue

            for method in self.VALID_HTTP_METHODS:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if isinstance(operation, dict):
                    description = operation.get("description", "").lower()
                    summary = operation.get("summary", "").lower()
                    if "deprecat" in description or "deprecat" in summary:
                        return True

        return False

    def _all_operations_secured(self, schema: Dict[str, Any]) -> bool:
        """Check if all operations have security requirements.

        Args:
            schema: OpenAPI schema

        Returns:
            True if all operations are secured
        """
        paths = schema.get("paths", {})
        global_security = schema.get("security", [])

        if global_security:
            return True

        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue

            for method in self.VALID_HTTP_METHODS:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if isinstance(operation, dict):
                    operation_security = operation.get("security")
                    if operation_security is None:
                        return False

        return True

    def _has_security_type(self, security_schemes: Dict[str, Any], criterion: str) -> bool:
        """Check if security schemes contain specified type.

        Args:
            security_schemes: Security schemes from components
            criterion: Criterion text containing security type

        Returns:
            True if security type found
        """
        criterion_lower = criterion.lower()

        for scheme in security_schemes.values():
            if not isinstance(scheme, dict):
                continue

            scheme_type = scheme.get("type", "").lower()

            if "api key" in criterion_lower and scheme_type == "apikey":
                return True
            if "oauth" in criterion_lower and scheme_type == "oauth2":
                return True
            if "bearer" in criterion_lower or "jwt" in criterion_lower:
                if scheme_type == "http" and scheme.get("scheme") == "bearer":
                    return True

        return False

    def _has_operation_descriptions(self, schema: Dict[str, Any]) -> bool:
        """Check if operations have descriptions.

        Args:
            schema: OpenAPI schema

        Returns:
            True if most operations have descriptions
        """
        paths = schema.get("paths", {})
        total_operations = 0
        operations_with_descriptions = 0

        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue

            for method in self.VALID_HTTP_METHODS:
                if method not in path_item:
                    continue

                total_operations += 1
                operation = path_item[method]
                if isinstance(operation, dict):
                    if operation.get("description") or operation.get("summary"):
                        operations_with_descriptions += 1

        if total_operations == 0:
            return False

        return operations_with_descriptions / total_operations >= 0.8

    def _has_response_schemas(self, schema: Dict[str, Any]) -> bool:
        """Check if operations have response schemas defined.

        Args:
            schema: OpenAPI schema

        Returns:
            True if most operations have response schemas
        """
        paths = schema.get("paths", {})
        total_operations = 0
        operations_with_schemas = 0

        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue

            for method in self.VALID_HTTP_METHODS:
                if method not in path_item:
                    continue

                total_operations += 1
                operation = path_item[method]
                if isinstance(operation, dict):
                    responses = operation.get("responses", {})
                    for response in responses.values():
                        if isinstance(response, dict):
                            content = response.get("content", {})
                            for media_type in content.values():
                                if isinstance(media_type, dict) and "schema" in media_type:
                                    operations_with_schemas += 1
                                    break
                            break

        if total_operations == 0:
            return False

        return operations_with_schemas / total_operations >= 0.8

    def _has_error_responses(self, schema: Dict[str, Any]) -> bool:
        """Check if operations define error responses.

        Args:
            schema: OpenAPI schema

        Returns:
            True if operations have error responses
        """
        paths = schema.get("paths", {})

        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue

            for method in self.VALID_HTTP_METHODS:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if isinstance(operation, dict):
                    responses = operation.get("responses", {})
                    error_codes = [code for code in responses.keys() if code.startswith(("4", "5"))]
                    if error_codes:
                        return True

        return False

    def _has_examples(self, schema: Dict[str, Any]) -> bool:
        """Check if schema contains examples.

        Args:
            schema: OpenAPI schema

        Returns:
            True if examples found
        """
        paths = schema.get("paths", {})

        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue

            for method in self.VALID_HTTP_METHODS:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if isinstance(operation, dict):
                    responses = operation.get("responses", {})
                    for response in responses.values():
                        if isinstance(response, dict):
                            content = response.get("content", {})
                            for media_type in content.values():
                                if isinstance(media_type, dict):
                                    if "example" in media_type or "examples" in media_type:
                                        return True

        return False
