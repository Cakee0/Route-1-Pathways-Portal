"""
main.py — FastAPI application entry point for Route 1 (v2)

User types:  farmer | organization (restaurant/grocery_store/food_shelf) | consumer
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all model classes so SQLAlchemy registers them before create_tables()
import models  # noqa: F401 — side-effect import; registers ORM metadata

from database import create_tables
from routers import auth, farmers, organizations, consumers, messaging
from routers.profiles import router as profiles_router
from routers.wishlist import router as wishlist_router
from routers.donations import router as donations_router
from routers.points import router as points_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Create / verify tables on startup (idempotent) ───────────────────────────
try:
    create_tables()
except Exception as exc:
    logger.error("Failed to create/verify tables on AWS RDS MySQL: %s", exc)
    raise SystemExit(1) from exc

# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Route 1 API",
    description=(
        "Minnesota-based food rescue marketplace connecting farmers, "
        "organizations (restaurants, grocery stores, food shelves), "
        "and consumers."
    ),
    version="2.0.0",
    contact={"name": "Route 1 Team", "email": "support@route1app.com"},
    license_info={"name": "MIT"},
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(farmers.router)
app.include_router(organizations.router)
app.include_router(consumers.router)
app.include_router(messaging.router)
app.include_router(profiles_router)
app.include_router(wishlist_router)
app.include_router(donations_router)
app.include_router(points_router)


# ── Health checks ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"], summary="Health check")
def root():
    return {"status": "ok", "app": "Route 1 API", "version": "2.0.0"}


@app.get("/health", tags=["Health"], summary="Detailed health check")
def health():
    return {
        "status":   "healthy",
        "database": "AWS RDS MySQL — mysqlRouteOne",
        "docs":     "/docs",
        "version":  "2.0.0",
    }
