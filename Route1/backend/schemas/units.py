"""
schemas/units.py — Shared quantity-unit whitelist.

Must stay in sync with the <select> options in the frontend
(farmer_dashboard.html and wishlist_manage.html).
"""

from typing import Literal

QuantityUnit = Literal["lbs", "kg", "bushels", "boxes", "crates", "bags", "units"]
