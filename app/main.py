import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine
from app.api.v1.patients import router as patient_router
from app.api.v1.doctors import router as doctor_router
from app.api.v1.appointments import router as appointment_router
from app.exceptions.exceptions import AppException

from app.core.exception_handler import (
    app_exception_handler,
    unexpected_exception_handler,
)

from app.core.logger import logger
from app.api.v1.auth import router as auth_router
from app.api.v1 import dashboard
from app.api.v1.ai import router as ai_router
from app.api.v1.doctor_schedule import router as doctor_schedule_router
from app.routes.notification_router import router as notification_router
from app.api.v1.emr import router as emr_router
from app.api.v1.admissions import router as admission_router
from app.api.v1.pharmacy import router as pharmacy_router
from app.api.v1.laboratory import router as laboratory_router
from app.api.v1.nursing import router as nursing_router
from app.api.v1.billing import router as billing_router
# NOTE: the background scheduler that polled the DB every minute for
# upcoming video appointments and pushed "video consultation starting
# soon" notifications has been turned off on purpose — only the clean
# login notification should fire now. See app/scheduler/appointment_scheduler.py
# if this ever needs to come back.


app = FastAPI(
    title="Clinic AI Assistant",
    version="1.0.0",
)

@app.on_event("startup")
def startup_event():
    # Video-appointment reminder scheduler intentionally not started —
    # see the note above the imports at the top of this file.

    # Create uploads directory for EMR reports
    uploads_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "uploads",
        "reports",
    )
    os.makedirs(uploads_dir, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("Clinic AI Backend Started")


# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────
app.include_router(patient_router)
app.include_router(doctor_schedule_router)
app.include_router(notification_router)
app.include_router(auth_router)
app.include_router(doctor_router)
app.include_router(ai_router)
app.include_router(appointment_router)
app.include_router(dashboard.router)
app.include_router(emr_router)
app.include_router(admission_router)
app.include_router(pharmacy_router)
app.include_router(laboratory_router)
app.include_router(nursing_router)
app.include_router(billing_router)

# ─────────────────────────────────────────────────────────────
# Exception Handlers
# ─────────────────────────────────────────────────────────────
app.add_exception_handler(
    AppException,
    app_exception_handler,
)

app.add_exception_handler(
    Exception,
    unexpected_exception_handler,
)

# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────
@app.get("/")
def home():
    return {
        "message": "Clinic AI Assistant Running"
    }


@app.get("/db-test")
def db_test():
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version();")).scalar()

    return {
        "status": "Connected Successfully",
        "postgres_version": version,
    }