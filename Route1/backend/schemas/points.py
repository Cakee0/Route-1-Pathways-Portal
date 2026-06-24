"""
schemas/points.py — Pydantic schemas for the Points & Rewards system.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel

from models import TIER_THRESHOLDS


# ── Individual ledger entry ───────────────────────────────────────────────────

class PointsLedgerEntry(BaseModel):
    id:          int
    points:      int
    amount_basis: float
    description: str | None
    created_at:  datetime

    model_config = {"from_attributes": True}


# ── Full points summary ───────────────────────────────────────────────────────

class TierInfo(BaseModel):
    tier:      int            # 1, 2, or 3
    threshold: int            # points needed to reach this tier
    reached:   bool           # has the consumer hit this tier?


class PointsSummaryResponse(BaseModel):
    consumer_id:   int
    total_points:  int
    tiers:         List[TierInfo]
    next_tier_pts: int | None   # points needed for next tier (None if max tier reached)
    history:       List[PointsLedgerEntry]

    model_config = {"from_attributes": True}

    @classmethod
    def build(cls, consumer_id: int, entries: List) -> "PointsSummaryResponse":
        """Factory: build a summary from a list of PointsLedger ORM objects."""
        total = sum(e.points for e in entries)
        tiers = [
            TierInfo(tier=i + 1, threshold=t, reached=(total >= t))
            for i, t in enumerate(TIER_THRESHOLDS)
        ]
        # Next tier not yet reached
        next_tier = next(
            (t for t in TIER_THRESHOLDS if total < t),
            None,
        )
        return cls(
            consumer_id=consumer_id,
            total_points=total,
            tiers=tiers,
            next_tier_pts=next_tier,
            history=[PointsLedgerEntry.model_validate(e) for e in entries],
        )
