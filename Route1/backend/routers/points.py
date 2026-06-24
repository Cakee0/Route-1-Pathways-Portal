"""
routers/points.py — Points & Rewards endpoints for consumers.

GET /points/me        — returns total points, tier progress, and transaction history
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserTypeEnum, PointsLedger
from routers.auth import get_current_user
from schemas import PointsSummaryResponse

router = APIRouter(prefix="/points", tags=["Points & Rewards"])


def _require_consumer(user: User) -> None:
    if user.user_type != UserTypeEnum.consumer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Points are only available for consumer accounts.",
        )


@router.get(
    "/me",
    response_model=PointsSummaryResponse,
    summary="Get current consumer's points balance and tier progress",
)
def get_my_points(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PointsSummaryResponse:
    _require_consumer(current_user)

    entries = (
        db.query(PointsLedger)
        .filter(PointsLedger.consumer_id == current_user.id)
        .order_by(PointsLedger.created_at.desc())
        .all()
    )

    return PointsSummaryResponse.build(
        consumer_id=current_user.id,
        entries=entries,
    )
