"""
schemas/profiles.py — the public view of a person on Route 1.

This is what one member sees of another: a face, a name, a line about who they
are, and their story. Deliberately NOT the account record — `email`,
`hashed_password`, `google_id` and `is_active` never appear here, because this
schema is returned for *other* users' ids.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PublicProfileResponse(BaseModel):
    """A member's profile, as shown to another logged-in member."""
    id:                int
    user_type:         str

    # Identity
    full_name:         Optional[str]
    organization_name: Optional[str]
    avatar_url:        Optional[str]
    tagline:           Optional[str]
    bio:               Optional[str]
    year_started:      Optional[int]

    # Where they are
    location_city:     Optional[str]
    location_region:   Optional[str]

    # Contact — already visible to logged-in members on the listing detail
    # page, so surfacing it here changes no boundary.
    phone:             Optional[str]

    member_since:      Optional[datetime]

    model_config = {"from_attributes": True}
