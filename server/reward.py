# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Reward calculation for the API Conformance Gym environment.

Primary reward is trajectory-aware shaping:
    R = (0.45 * Q) + (0.35 * T) + (0.20 * P) - K
where:
    Q = Global schema quality from validator scores
    T = Active task grader score
    P = Positive progress delta over prior step
    K = Explicit behavior penalty

The static validity/best-practices/error formula is retained as a legacy helper.

For the Migration Environment, the MigrationRewardCalculator implements:
    R = (0.45 * C) + (0.25 * T) + (0.20 * Q) + (0.10 * P) - B - K
where:
    C = Contract preservation pass rate
    T = Ticket satisfaction score
    Q = Schema quality score
    P = Progress improvement delta
    B = Breaking change penalty
    K = Behavior penalty
"""

try:
    from ..models import ValidationResult
except ImportError:
    # Handle both relative and absolute imports
    import sys
    import os

    # Add parent directory to path for absolute imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    try:
        from models import ValidationResult
    except ImportError:
        # Last resort - try direct import
        from api_conformance_gym.models import ValidationResult


class RewardCalculator:
    """Calculates rewards based on validation results."""

    MAX_ERRORS = 20  # Maximum errors before penalty is fully applied

    @staticmethod
    def calculate(validation_result: ValidationResult) -> float:
        """Legacy static reward helper for compatibility.

        Args:
            validation_result: ValidationResult from the validation pipeline

        Returns:
            Reward value in range [-0.2, 1.0]
        """
        # Extract scores from validation result
        validity_score = validation_result.validity_score
        best_practices_score = validation_result.best_practices_score
        error_count = len(validation_result.errors)

        # Normalize error count to [0.0, 1.0]
        normalized_error_count = min(1.0, error_count / RewardCalculator.MAX_ERRORS)

        # Apply reward formula
        reward = (
            (validity_score * 0.6)
            + (best_practices_score * 0.4)
            - (normalized_error_count * 0.2)
        )

        # Ensure reward is within bounds [-0.2, 1.0]
        reward = max(-0.2, min(1.0, reward))

        return reward

    @staticmethod
    def calculate_shaped(
        validation_result: ValidationResult,
        task_score: float,
        progress_delta: float,
        penalty: float = 0.0,
    ) -> float:
        """Calculate a trajectory-aware reward in [0.0, 1.0].

        Composition:
          - 45% global schema quality from validator scores
          - 35% active task grader score (easy/medium/hard)
          - 20% positive progress delta over previous step
          - subtract explicit behavior penalties
        """
        quality = (validation_result.validity_score * 0.55) + (
            validation_result.best_practices_score * 0.45
        )

        # Clamp external components for safety.
        task_score = max(0.0, min(1.0, task_score))
        progress_delta = max(0.0, min(1.0, progress_delta))
        penalty = max(0.0, min(0.5, penalty))

        reward = (
            (quality * 0.45) + (task_score * 0.35) + (progress_delta * 0.20) - penalty
        )
        return max(0.0, min(1.0, reward))


class MigrationRewardCalculator:
    """Calculates rewards for the Migration Environment with multi-component weighting.
    
    Implements the reward calculation specified in Requirements 4.1-4.6:
    - Contract preservation: 45%
    - Ticket satisfaction: 25%
    - Schema quality: 20%
    - Progress improvement: 10%
    - Subtract breaking change penalties and behavior penalties
    - Clamp final rewards to [0.0, 1.0]
    """

    # Component weights (Requirements 4.1-4.4)
    WEIGHT_CONTRACT = 0.45
    WEIGHT_TICKET = 0.25
    WEIGHT_QUALITY = 0.20
    WEIGHT_PROGRESS = 0.10

    # Quality sub-component weights
    QUALITY_VALIDITY_WEIGHT = 0.55
    QUALITY_BEST_PRACTICES_WEIGHT = 0.45

    @staticmethod
    def calculate_reward(
        contract_pass_rate: float,
        ticket_score: float,
        validity_score: float,
        best_practices_score: float,
        progress_delta: float,
        breaking_penalty: float = 0.0,
        behavior_penalty: float = 0.0,
    ) -> float:
        """Calculate the final reward for a migration step.

        Args:
            contract_pass_rate: Contract preservation score [0.0, 1.0]
            ticket_score: Ticket satisfaction score [0.0, 1.0]
            validity_score: Schema validity score [0.0, 1.0]
            best_practices_score: Schema best practices score [0.0, 1.0]
            progress_delta: Progress improvement delta [0.0, 1.0]
            breaking_penalty: Penalty for breaking changes [0.0, inf)
            behavior_penalty: Penalty for undesirable behavior [0.0, inf)

        Returns:
            Final reward clamped to [0.0, 1.0]
        """
        # Clamp inputs for numerical stability.
        contract_pass_rate = max(0.0, min(1.0, contract_pass_rate))
        ticket_score = max(0.0, min(1.0, ticket_score))
        validity_score = max(0.0, min(1.0, validity_score))
        best_practices_score = max(0.0, min(1.0, best_practices_score))
        progress_delta = max(0.0, min(1.0, progress_delta))

        # Calculate quality score from validity and best practices
        quality_score = (
            MigrationRewardCalculator.QUALITY_VALIDITY_WEIGHT * validity_score
            + MigrationRewardCalculator.QUALITY_BEST_PRACTICES_WEIGHT * best_practices_score
        )

        # Calculate base reward with weighted components (Requirements 4.1-4.4)
        reward = (
            MigrationRewardCalculator.WEIGHT_CONTRACT * contract_pass_rate
            + MigrationRewardCalculator.WEIGHT_TICKET * ticket_score
            + MigrationRewardCalculator.WEIGHT_QUALITY * quality_score
            + MigrationRewardCalculator.WEIGHT_PROGRESS * progress_delta
        )

        # Subtract penalties (Requirement 4.5)
        # Cap penalties to avoid fully saturating reward at zero for most steps.
        capped_breaking_penalty = min(0.25, max(0.0, breaking_penalty))
        capped_behavior_penalty = min(0.15, max(0.0, behavior_penalty))
        reward = reward - capped_breaking_penalty - capped_behavior_penalty

        # Clamp to valid range (Requirement 4.6)
        reward = max(0.0, min(1.0, reward))

        return reward
