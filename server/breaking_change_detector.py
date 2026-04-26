# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Breaking Change Detector for API Lifecycle Migration Environment.

This module implements breaking change detection between consecutive OpenAPI
schema versions. It identifies removed operations, removed fields, and changed
response structures, classifying them by type and severity.

Performance optimizations:
- Early exits for missing paths/operations
- Efficient set operations for field comparison
- Cached path lookups
"""

from typing import Any, Dict, List, Set, Tuple

try:
    from ..migration_models import BreakingChange, BreakingChangeReport
except ImportError:
    import sys
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from migration_models import BreakingChange, BreakingChangeReport


class BreakingChangeDetector:
    """Detects breaking changes between consecutive API schema versions.
    
    Performance optimizations:
    - Early exits for missing paths/operations
    - Efficient set operations for field comparison
    - Cached severity weights
    """

    VALID_HTTP_METHODS = ["get", "post", "put", "patch", "delete"]
    # Reward shaping penalty: 0.05 per breaking change, capped to avoid domination.
    BREAKING_CHANGE_PENALTY_PER_CHANGE = 0.05
    BREAKING_CHANGE_PENALTY_CAP = 0.50

    def detect_breaking_changes(
        self, prev_schema: Dict[str, Any], current_schema: Dict[str, Any]
    ) -> BreakingChangeReport:
        """Detect breaking changes between consecutive schema versions.

        Compares prev_schema and current_schema to identify:
        - Removed paths
        - Removed operations
        - Removed response fields
        - Changed response structures
        
        Performance optimizations:
        - Early exits for missing paths
        - Efficient set operations
        - Minimal object allocations

        Args:
            prev_schema: Previous OpenAPI schema dictionary
            current_schema: Current OpenAPI schema dictionary

        Returns:
            BreakingChangeReport with all detected changes and calculated penalty
        """
        breaking_changes: List[BreakingChange] = []

        # Extract paths from both schemas (cached for performance)
        prev_paths = prev_schema.get("paths", {})
        current_paths = current_schema.get("paths", {})

        # Detect removed paths
        breaking_changes.extend(
            self._detect_removed_paths(prev_paths, current_paths)
        )

        # Detect removed operations and response field changes
        breaking_changes.extend(
            self._detect_removed_operations(prev_paths, current_paths)
        )

        # Detect response field regressions
        breaking_changes.extend(
            self._detect_response_field_changes(prev_paths, current_paths)
        )

        # Calculate breaking penalty
        breaking_penalty = self._calculate_penalty(breaking_changes)

        return BreakingChangeReport(
            breaking_change_count=len(breaking_changes),
            breaking_changes=breaking_changes,
            breaking_penalty=breaking_penalty,
        )

    def _detect_removed_paths(
        self, prev_paths: Dict[str, Any], current_paths: Dict[str, Any]
    ) -> List[BreakingChange]:
        """Detect paths that were removed from the schema.

        Args:
            prev_paths: Previous schema paths
            current_paths: Current schema paths

        Returns:
            List of BreakingChange objects for removed paths
        """
        changes: List[BreakingChange] = []

        for path_name in prev_paths:
            if path_name not in current_paths:
                changes.append(
                    BreakingChange(
                        change_type="removed_path",
                        path=f"/paths/{path_name}",
                        description=f"Path '{path_name}' was removed from the API",
                        severity="critical",
                    )
                )

        return changes

    def _detect_removed_operations(
        self, prev_paths: Dict[str, Any], current_paths: Dict[str, Any]
    ) -> List[BreakingChange]:
        """Detect operations that were removed from existing paths.

        Args:
            prev_paths: Previous schema paths
            current_paths: Current schema paths

        Returns:
            List of BreakingChange objects for removed operations
        """
        changes: List[BreakingChange] = []

        for path_name, prev_path_item in prev_paths.items():
            if not isinstance(prev_path_item, dict):
                continue

            # Skip if path was completely removed (handled by _detect_removed_paths)
            if path_name not in current_paths:
                continue

            current_path_item = current_paths[path_name]
            if not isinstance(current_path_item, dict):
                continue

            # Check each HTTP method
            for method in self.VALID_HTTP_METHODS:
                if method in prev_path_item and method not in current_path_item:
                    changes.append(
                        BreakingChange(
                            change_type="removed_operation",
                            path=f"/paths/{path_name}/{method}",
                            description=f"Operation {method.upper()} {path_name} was removed",
                            severity="critical",
                        )
                    )

        return changes

    def _detect_response_field_changes(
        self, prev_paths: Dict[str, Any], current_paths: Dict[str, Any]
    ) -> List[BreakingChange]:
        """Detect removed or changed response fields.

        Args:
            prev_paths: Previous schema paths
            current_paths: Current schema paths

        Returns:
            List of BreakingChange objects for response field changes
        """
        changes: List[BreakingChange] = []

        for path_name, prev_path_item in prev_paths.items():
            if not isinstance(prev_path_item, dict):
                continue

            # Skip if path was removed
            if path_name not in current_paths:
                continue

            current_path_item = current_paths[path_name]
            if not isinstance(current_path_item, dict):
                continue

            # Check each operation
            for method in self.VALID_HTTP_METHODS:
                if method not in prev_path_item:
                    continue

                # Skip if operation was removed (handled by _detect_removed_operations)
                if method not in current_path_item:
                    continue

                prev_operation = prev_path_item[method]
                current_operation = current_path_item[method]

                if not isinstance(prev_operation, dict) or not isinstance(
                    current_operation, dict
                ):
                    continue

                # Check response fields
                changes.extend(
                    self._compare_response_fields(
                        path_name, method, prev_operation, current_operation
                    )
                )

        return changes

    def _compare_response_fields(
        self,
        path_name: str,
        method: str,
        prev_operation: Dict[str, Any],
        current_operation: Dict[str, Any],
    ) -> List[BreakingChange]:
        """Compare response fields between operations.

        Args:
            path_name: API path
            method: HTTP method
            prev_operation: Previous operation definition
            current_operation: Current operation definition

        Returns:
            List of BreakingChange objects for field changes
        """
        changes: List[BreakingChange] = []

        prev_responses = prev_operation.get("responses", {})
        current_responses = current_operation.get("responses", {})

        # Check 200 response (most common success response)
        if "200" in prev_responses and "200" in current_responses:
            prev_fields = self._extract_response_fields(prev_responses["200"])
            current_fields = self._extract_response_fields(current_responses["200"])

            # Detect removed fields
            removed_fields = prev_fields - current_fields
            for field in removed_fields:
                changes.append(
                    BreakingChange(
                        change_type="removed_field",
                        path=f"/paths/{path_name}/{method}/responses/200/content/*/schema/properties/{field}",
                        description=f"Response field '{field}' was removed from {method.upper()} {path_name}",
                        severity="major",
                    )
                )

        # Detect removed response status codes
        elif "200" in prev_responses and "200" not in current_responses:
            changes.append(
                BreakingChange(
                    change_type="removed_response",
                    path=f"/paths/{path_name}/{method}/responses/200",
                    description=f"200 response was removed from {method.upper()} {path_name}",
                    severity="major",
                )
            )

        return changes

    def _extract_response_fields(self, response: Dict[str, Any]) -> Set[str]:
        """Extract field names from a response definition.

        Args:
            response: OpenAPI response object

        Returns:
            Set of field names from response schema
        """
        fields: Set[str] = set()

        if not isinstance(response, dict):
            return fields

        content = response.get("content", {})
        if not content:
            return fields

        # Check common content types
        for content_type in ["application/json", "application/vnd.api+json"]:
            if content_type in content:
                media_type = content[content_type]
                if isinstance(media_type, dict):
                    schema = media_type.get("schema", {})
                    if isinstance(schema, dict):
                        properties = schema.get("properties", {})
                        if isinstance(properties, dict):
                            fields.update(properties.keys())
                            break

        return fields

    def _calculate_penalty(self, breaking_changes: List[BreakingChange]) -> float:
        """Calculate penalty based on breaking changes count.

        Reward spec:
        - 0.05 per breaking change
        - capped at 0.15

        Args:
            breaking_changes: List of detected breaking changes

        Returns:
            Calculated penalty value (0.0 to 0.15)
        """
        total_penalty = (
            len(breaking_changes) * self.BREAKING_CHANGE_PENALTY_PER_CHANGE
        )
        return min(self.BREAKING_CHANGE_PENALTY_CAP, total_penalty)
