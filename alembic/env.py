import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from app.core.database import Base
from app.core.config import DATABASE_URL
from app.models.patient import Patient
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.user import User
from app.models.doctor_schedule import DoctorSchedule
from app.models.medical_history import MedicalHistory
from app.models.patient_report import PatientReport
from app.models.prescription import Prescription
from app.models.prescription_item import PrescriptionItem
from app.models.doctor_note import DoctorNote
from app.models.patient_vital import PatientVital
from app.models.patient_allergy import PatientAllergy
from app.models.diagnosis import Diagnosis
from app.models.ward import Ward
from app.models.bed import Bed
from app.models.admission import Admission
from app.models.admission_note import AdmissionNote
from app.models.medicine import Medicine
from app.models.pharmacy_order import PharmacyOrder
from app.models.medication_administration import MedicationAdministration
from app.models.lab_test import LabTest
from app.models.lab_order import LabOrder
from app.models.lab_result import LabResult
from app.models.billing import Bill, BillItem


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# Override the hardcoded alembic.ini URL with the real DATABASE_URL from
# the environment (.env locally, Railway's injected variable in prod).
# Without this, `alembic upgrade head` always tries to connect to the
# localhost placeholder baked into alembic.ini and fails on any real host.
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
