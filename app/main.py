"""
FastAPI application — Driver Trip Tracking & Control System.

Entrypoint: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.models import User, Vehicle, DriverVehicleAssignment, Trip, AuditLog  # noqa: F401 — register models
from app.routers import auth, admin_users, admin_vehicles, admin_trips, driver, audit


# ── Lifespan (create tables on startup) ──────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables on startup (dev convenience — use Alembic in production)."""
    Base.metadata.create_all(bind=engine)
    yield


# ── App ───────────────────────────────────────────────────

app = FastAPI(
    title="Driver Trip Tracking & Control System",
    description=(
        "Backend API for the Driver Trip Tracking & Control System. "
        "Provides endpoints for the mobile driver app and the admin web dashboard."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (allow mobile app & web dashboard) ──────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ─────────────────────────────────────

app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(admin_vehicles.router)
app.include_router(admin_trips.router)
app.include_router(driver.router)
app.include_router(audit.router)


# ── Health Check ──────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "service": "Driver Trip Tracking & Control System"}
