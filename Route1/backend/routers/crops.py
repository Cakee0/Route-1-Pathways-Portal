"""
routers/crops.py — Crop request CRUD endpoints
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import CropRequest, User, UserTypeEnum
from routers.auth import get_current_user
from schemas import CropRequestCreate, CropRequestResponse, CropRequestStatusUpdate

router = APIRouter(prefix="/crops", tags=["Crop Requests"])


def _require_org(user: User):
    """Raise 403 if the user is not an organization."""
    if user.user_type != UserTypeEnum.organization:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizations can perform this action.",
        )


def _build_response(req: CropRequest) -> CropRequestResponse:
    """Helper: merge CropRequest + organization profile into response schema."""
    return CropRequestResponse(
        id                  = req.id,
        organization_id     = req.organization_id,
        crops_low_in_stock  = req.crops_low_in_stock,
        nice_to_have_crops  = req.nice_to_have_crops,
        fulfillment_status  = req.fulfillment_status,
        created_at          = req.created_at,
        updated_at          = req.updated_at,
        organization_name   = req.organization.organization_name if req.organization else None,
        city                = req.organization.city if req.organization else None,
        state               = req.organization.state if req.organization else None,
    )


# ── POST /crops/request ───────────────────────────────────────────────────────
@router.post(
    "/request",
    response_model=CropRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Organization submits a new crop request",
)
def submit_crop_request(
    payload: CropRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org(current_user)

    new_req = CropRequest(
        organization_id    = current_user.id,
        crops_low_in_stock = ",".join(payload.crops_low_in_stock),
        nice_to_have_crops = payload.nice_to_have_crops,
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)
    return _build_response(new_req)


# ── GET /crops/requests ───────────────────────────────────────────────────────
@router.get(
    "/requests",
    response_model=List[CropRequestResponse],
    summary="List crop requests — farmers see all pending requests; orgs see their own",
)
def list_crop_requests(
    city: Optional[str]  = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by fulfillment status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CropRequest).join(CropRequest.organization)

    if current_user.user_type == UserTypeEnum.organization:
        # Organizations only see their own requests
        query = query.filter(CropRequest.organization_id == current_user.id)
    # Farmers (and donors) see all requests

    if city:
        query = query.filter(User.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(User.state.ilike(f"%{state}%"))
    if status_filter:
        query = query.filter(CropRequest.fulfillment_status == status_filter)

    requests = query.order_by(CropRequest.created_at.desc()).all()
    return [_build_response(r) for r in requests]


# ── GET /crops/requests/{id} ─────────────────────────────────────────────────
@router.get(
    "/requests/{request_id}",
    response_model=CropRequestResponse,
    summary="Get a single crop request by ID",
)
def get_crop_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req = db.query(CropRequest).filter(CropRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Crop request not found.")

    # Organizations can only view their own
    if (
        current_user.user_type == UserTypeEnum.organization
        and req.organization_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    return _build_response(req)


# ── PATCH /crops/requests/{id}/status ────────────────────────────────────────
@router.patch(
    "/requests/{request_id}/status",
    response_model=CropRequestResponse,
    summary="Update the fulfillment status of a crop request",
)
def update_fulfillment_status(
    request_id: int,
    payload: CropRequestStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req = db.query(CropRequest).filter(CropRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Crop request not found.")

    # Only the owning org or a farmer can update status
    if (
        current_user.user_type == UserTypeEnum.organization
        and req.organization_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    req.fulfillment_status = payload.fulfillment_status
    db.commit()
    db.refresh(req)
    return _build_response(req)


# ── DELETE /crops/requests/{id} ───────────────────────────────────────────────
@router.delete(
    "/requests/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a crop request (organization only)",
)
def delete_crop_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org(current_user)
    req = db.query(CropRequest).filter(
        CropRequest.id == request_id,
        CropRequest.organization_id == current_user.id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Crop request not found.")

    db.delete(req)
    db.commit()
