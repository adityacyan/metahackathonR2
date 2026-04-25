# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Ticket Progression Manager for API Lifecycle Migration Environment.

This module implements ticket queue management and progression logic for
the migration environment. It handles ticket advancement when satisfaction
thresholds are met and tracks completion progress.
"""

import logging
from typing import List, Optional

# Configure logging for error tracking
logger = logging.getLogger(__name__)

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


class TicketProgressionManager:
    """Manages ticket queue and progression logic for migration episodes."""

    SATISFACTION_THRESHOLD = 0.8

    def __init__(self, ticket_queue: List[MigrationTicket]):
        """Initialize ticket progression manager.

        Handles malformed ticket data gracefully (Requirement 10.4).

        Args:
            ticket_queue: List of migration tickets for the episode
        """
        # Validate and filter ticket queue for malformed data
        validated_tickets = []
        for i, ticket in enumerate(ticket_queue):
            try:
                # Validate ticket has required fields
                if not ticket.ticket_id or not ticket.title:
                    logger.warning(
                        f"Skipping malformed ticket at index {i}: missing required fields",
                        extra={"ticket": ticket}
                    )
                    continue

                if not ticket.acceptance_criteria:
                    logger.warning(
                        f"Ticket {ticket.ticket_id} has no acceptance criteria, using default",
                        extra={"ticket_id": ticket.ticket_id}
                    )

                validated_tickets.append(ticket)

            except Exception as e:
                logger.error(
                    f"Error validating ticket at index {i}: {e}",
                    exc_info=True,
                    extra={"index": i}
                )
                # Skip malformed ticket and continue

        self.ticket_queue = validated_tickets.copy()
        self.total_tickets = len(validated_tickets)
        self.tickets_completed = 0
        self.active_ticket: Optional[MigrationTicket] = None

        if self.ticket_queue:
            self.active_ticket = self.ticket_queue.pop(0)
            logger.info(
                f"Initialized with {self.total_tickets} tickets, active: {self.active_ticket.ticket_id if self.active_ticket else 'None'}"
            )
        else:
            logger.warning("Initialized with empty ticket queue")

    def check_and_advance(self, satisfaction_score: float) -> bool:
        """Check if current ticket is satisfied and advance if threshold met.

        Args:
            satisfaction_score: Current ticket satisfaction score [0.0, 1.0]

        Returns:
            True if ticket was advanced, False otherwise
        """
        if self.active_ticket is None:
            return False

        try:
            if satisfaction_score >= self.SATISFACTION_THRESHOLD:
                logger.info(
                    f"Ticket {self.active_ticket.ticket_id} satisfied with score {satisfaction_score:.2f}",
                    extra={"ticket_id": self.active_ticket.ticket_id, "score": satisfaction_score}
                )
                self.tickets_completed += 1

                if self.ticket_queue:
                    self.active_ticket = self.ticket_queue.pop(0)
                    logger.info(
                        f"Advanced to ticket {self.active_ticket.ticket_id}",
                        extra={"ticket_id": self.active_ticket.ticket_id}
                    )
                else:
                    self.active_ticket = None
                    logger.info("All tickets completed")

                return True

        except Exception as e:
            logger.error(
                f"Error during ticket advancement: {e}",
                exc_info=True,
                extra={"active_ticket": self.active_ticket.ticket_id if self.active_ticket else None}
            )
            # Don't advance on error, maintain stability
            return False

        return False

    def is_all_tickets_completed(self) -> bool:
        """Check if all tickets have been completed.

        Returns:
            True if all tickets completed, False otherwise
        """
        return self.active_ticket is None and self.tickets_completed == self.total_tickets

    def get_active_ticket(self) -> Optional[MigrationTicket]:
        """Get the currently active ticket.

        Returns:
            Active ticket or None if all completed
        """
        return self.active_ticket

    def get_completion_status(self) -> tuple:
        """Get ticket completion status.

        Returns:
            Tuple of (tickets_completed, total_tickets)
        """
        return (self.tickets_completed, self.total_tickets)

    def get_remaining_tickets_count(self) -> int:
        """Get count of remaining tickets in queue.

        Returns:
            Number of tickets remaining (including active ticket)
        """
        remaining = len(self.ticket_queue)
        if self.active_ticket is not None:
            remaining += 1
        return remaining

    def reset(self, ticket_queue: List[MigrationTicket]) -> None:
        """Reset the progression manager with a new ticket queue.

        Args:
            ticket_queue: New list of migration tickets
        """
        self.ticket_queue = ticket_queue.copy()
        self.total_tickets = len(ticket_queue)
        self.tickets_completed = 0
        self.active_ticket = None

        if self.ticket_queue:
            self.active_ticket = self.ticket_queue.pop(0)
