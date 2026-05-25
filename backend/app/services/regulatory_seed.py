"""Regulatory corpus seed shim.

The actual MoJ sync runs as part of the async startup hook in
backend/app/main.py (schedule_daily), because FastAPI's sync startup
hook already has an event loop running and asyncio.run() cannot nest
into it. This function is kept so the startup sequence stays
explicit but the heavy lifting moved upstairs.

See docs/MOJ_CONNECTOR.md for the discovery write-up and rationale.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def seed_regulatory_corpus(db: Session) -> None:
    # Intentionally a no-op. The MoJ sync is awaited in
    # main.schedule_daily so it runs in the right async context.
    logger.info("regulatory_seed: deferring to async MoJ sync in schedule_daily")
