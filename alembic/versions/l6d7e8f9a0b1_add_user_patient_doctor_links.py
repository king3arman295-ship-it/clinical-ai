"""add missing user<->patient/doctor link columns

The User model (app/models/user.py) declares patient_id and doctor_id,
and the Patient/Doctor models (app/models/patient.py, app/models/doctor.py)
declare user_id — but no migration ever created users.patient_id /
users.doctor_id, and patients.user_id was added in 395620683f54 then
dropped again in 99993d81a84f. doctors.user_id was never created at all.

This migration brings the database in line with the current models so
login (users.patient_id / users.doctor_id are selected on every query)
and patient/doctor registration (which write patients.user_id /
doctors.user_id) stop failing with UndefinedColumn.

Revision ID: l6d7e8f9a0b1
Revises: k5c6d7e8f9a0
Create Date: 2026-08-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "l6d7e8f9a0b1"
down_revision: Union[str, None] = "k5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # -----------------------------------------------------------------
    # users.patient_id / users.doctor_id
    # -----------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column("patient_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_patient_id",
        "users",
        "patients",
        ["patient_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_users_patient_id",
        "users",
        ["patient_id"],
    )

    op.add_column(
        "users",
        sa.Column("doctor_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_doctor_id",
        "users",
        "doctors",
        ["doctor_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_users_doctor_id",
        "users",
        ["doctor_id"],
    )

    # -----------------------------------------------------------------
    # patients.user_id (re-add; dropped in 99993d81a84f)
    # -----------------------------------------------------------------
    op.add_column(
        "patients",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_patients_user_id",
        "patients",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_patients_user_id",
        "patients",
        ["user_id"],
    )

    # -----------------------------------------------------------------
    # doctors.user_id (never existed in the database)
    # -----------------------------------------------------------------
    op.add_column(
        "doctors",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_doctors_user_id",
        "doctors",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_doctors_user_id",
        "doctors",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint("uq_doctors_user_id", "doctors", type_="unique")
    op.drop_constraint("fk_doctors_user_id", "doctors", type_="foreignkey")
    op.drop_column("doctors", "user_id")

    op.drop_constraint("uq_patients_user_id", "patients", type_="unique")
    op.drop_constraint("fk_patients_user_id", "patients", type_="foreignkey")
    op.drop_column("patients", "user_id")

    op.drop_constraint("uq_users_doctor_id", "users", type_="unique")
    op.drop_constraint("fk_users_doctor_id", "users", type_="foreignkey")
    op.drop_column("users", "doctor_id")

    op.drop_constraint("uq_users_patient_id", "users", type_="unique")
    op.drop_constraint("fk_users_patient_id", "users", type_="foreignkey")
    op.drop_column("users", "patient_id")