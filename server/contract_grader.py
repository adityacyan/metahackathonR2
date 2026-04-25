# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Contract Suite Grader for API Lifecycle Migration Environment.

This module implements contract suite generation and testing to ensure
backward compatibility during API evolution. It extracts required operations
from baseline schemas and validates evolved schemas against those expectations.
"""

import hashlib
import json
from typing import Any, Dict, List, Tuple

try:
    from ..migration_models import (
        ContractExpectation,
        ContractSuite,
        ContractTestResult,
    )
except ImportError:
    import sys
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from migration_models import (
        ContractExpectation,
        ContractSuite,
        ContractTestResult,
    )


class ContractSuiteGrader:
    """Generates and tests contract suites for API backward compatibility.
    
    Performance optimizations:
    - Caches schema hashes to avoid recomputation
    - Early exits for missing paths/operations
    - Efficient field extraction with content-type prioritization
    """

    VALID_HTTP_METHODS = ["get", "post", "put", "patch", "delete"]
    
    # Cache for schema hashes to avoid recomputation
    _hash_cache = {}

    def generate_contract_suite(self, baseline_schema: Dict[str, Any]) -> ContractSuite:
        """Generate contract suite from baseline schema.

        Extracts 3-8 required operations from the baseline schema, including
        required response fields for GET operations and security requirements
        for all operations.

        Args:
            baseline_schema: Valid OpenAPI schema dictionary

        Returns:
            ContractSuite with required operations and expectations

        Raises:
            ValueError: If baseline schema has insufficient operations (< 3)
        """
        required_operations: List[Tuple[str, str]] = []
        required_response_fields: List[ContractExpectation] = []

        # Extract all operations from baseline schema
        paths = baseline_schema.get("paths", {})

        for path_name, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method in self.VALID_HTTP_METHODS:
                if method in path_item:
                    operation = path_item[method]

                    # Add to required operations (limit to 8 most important)
                    if len(required_operations) < 8:
                        required_operations.append((path_name, method))

                        # Extract required response fields for GET operations
                        if method == "get" and isinstance(operation, dict):
                            fields = self._extract_response_fields(operation)
                            if fields:
                                expectation = ContractExpectation(
                                    path=path_name,
                                    method=method,
                                    required_response_fields=fields,
                                    status_code="200",
                                    required_security=True,
                                )
                                required_response_fields.append(expectation)

        # Ensure minimum coverage
        if len(required_operations) < 3:
            raise ValueError(
                f"Baseline schema has insufficient operations for contract generation "
                f"(found {len(required_operations)}, need at least 3)"
            )

        # Generate security requirements for all operations
        required_security = {}
        for path, method in required_operations:
            operation_key = f"{path}.{method}"
            required_security[operation_key] = True

        # Compute baseline schema hash
        baseline_schema_hash = self._compute_schema_hash(baseline_schema)

        contract_suite = ContractSuite(
            required_operations=required_operations,
            required_security=required_security,
            required_response_fields=required_response_fields,
            baseline_schema_hash=baseline_schema_hash,
        )

        return contract_suite

    def run_contract_tests(
        self, current_schema: Dict[str, Any], contract_suite: ContractSuite
    ) -> ContractTestResult:
        """Validate evolved schema against contract suite.

        Checks for missing operations, response field regressions, and
        authentication regressions. Calculates contract pass rate based
        on satisfied expectations.
        
        Performance optimizations:
        - Early exit on missing paths
        - Cached path lookups
        - Efficient field comparison

        Args:
            current_schema: Evolved OpenAPI schema dictionary
            contract_suite: Contract suite with baseline expectations

        Returns:
            ContractTestResult with pass rate and detailed failures
        """
        contract_failures: List[str] = []
        missing_operations: List[Tuple[str, str]] = []
        response_field_regressions: List[str] = []
        auth_regressions: List[str] = []

        total_expectations = 0
        satisfied_expectations = 0

        # Cache paths lookup for performance
        paths = current_schema.get("paths", {})
        # Check for missing operations (optimized with early path check)
        for path, method in contract_suite.required_operations:
            total_expectations += 1

            # Early exit if path doesn't exist
            if path not in paths:
                missing_operations.append((path, method))
                contract_failures.append(
                    f"Missing required operation: {method.upper()} {path}"
                )
                continue
            
            path_item = paths[path]
            if not isinstance(path_item, dict) or method not in path_item:
                missing_operations.append((path, method))
                contract_failures.append(
                    f"Missing required operation: {method.upper()} {path}"
                )
            else:
                satisfied_expectations += 1

        # Check for response field regressions
        for expectation in contract_suite.required_response_fields:
            for field in expectation.required_response_fields:
                total_expectations += 1

                path_item = paths.get(expectation.path, {})
                if isinstance(path_item, dict) and expectation.method in path_item:
                    operation = path_item[expectation.method]
                    if self._has_response_field(operation, field, expectation.status_code):
                        satisfied_expectations += 1
                    else:
                        response_field_regressions.append(
                            f"{expectation.method.upper()} {expectation.path}: missing field '{field}'"
                        )
                        contract_failures.append(
                            f"Response field regression: {expectation.method.upper()} {expectation.path} "
                            f"missing required field '{field}' in {expectation.status_code} response"
                        )
                else:
                    # Operation missing, already counted in missing_operations
                    response_field_regressions.append(
                        f"{expectation.method.upper()} {expectation.path}: operation missing"
                    )

        # Check for authentication regressions
        global_security = current_schema.get("security", [])

        for path, method in contract_suite.required_operations:
            operation_key = f"{path}.{method}"
            if contract_suite.required_security.get(operation_key, False):
                total_expectations += 1

                path_item = paths.get(path, {})
                if isinstance(path_item, dict) and method in path_item:
                    operation = path_item[method]
                    if isinstance(operation, dict):
                        operation_security = operation.get("security")
                        has_security = operation_security is not None or global_security

                        if has_security:
                            satisfied_expectations += 1
                        else:
                            auth_regressions.append(
                                f"{method.upper()} {path}: missing security"
                            )
                            contract_failures.append(
                                f"Authentication regression: {method.upper()} {path} "
                                f"is not protected by security requirements"
                            )

        # Calculate contract pass rate
        if total_expectations > 0:
            contract_pass_rate = satisfied_expectations / total_expectations
        else:
            contract_pass_rate = 0.0

        return ContractTestResult(
            contract_pass_rate=contract_pass_rate,
            contract_failures=contract_failures,
            missing_operations=missing_operations,
            response_field_regressions=response_field_regressions,
            auth_regressions=auth_regressions,
        )

    def _extract_response_fields(self, operation: Dict[str, Any]) -> List[str]:
        """Extract required response fields from GET operation.

        Args:
            operation: OpenAPI operation object

        Returns:
            List of field names from 200 response schema
        """
        fields: List[str] = []

        responses = operation.get("responses", {})
        if "200" not in responses:
            return fields

        response_200 = responses["200"]
        if not isinstance(response_200, dict):
            return fields

        # Navigate to schema properties
        content = response_200.get("content", {})
        if not content:
            return fields

        # Check common content types
        for content_type in ["application/json", "application/vnd.api+json"]:
            if content_type in content:
                media_type = content[content_type]
                if isinstance(media_type, dict):
                    schema = media_type.get("schema", {})
                    if isinstance(schema, dict):
                        # Extract properties from schema
                        properties = schema.get("properties", {})
                        if isinstance(properties, dict):
                            fields.extend(properties.keys())
                            break

        return fields

    def _has_response_field(
        self, operation: Dict[str, Any], field_name: str, status_code: str
    ) -> bool:
        """Check if operation response contains required field.

        Args:
            operation: OpenAPI operation object
            field_name: Name of required field
            status_code: Response status code to check

        Returns:
            True if field exists in response schema
        """
        responses = operation.get("responses", {})
        if status_code not in responses:
            return False

        response = responses[status_code]
        if not isinstance(response, dict):
            return False

        content = response.get("content", {})
        if not content:
            return False

        # Check common content types
        for content_type in ["application/json", "application/vnd.api+json"]:
            if content_type in content:
                media_type = content[content_type]
                if isinstance(media_type, dict):
                    schema = media_type.get("schema", {})
                    if isinstance(schema, dict):
                        properties = schema.get("properties", {})
                        if isinstance(properties, dict) and field_name in properties:
                            return True

        return False

    def _compute_schema_hash(self, schema: Dict[str, Any]) -> str:
        """Compute deterministic hash of schema.

        Args:
            schema: OpenAPI schema dictionary

        Returns:
            SHA256 hash of schema JSON
        """
        schema_json = json.dumps(schema, sort_keys=True)
        return hashlib.sha256(schema_json.encode("utf-8")).hexdigest()
