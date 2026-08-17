
"""add patient_reminded to medication_course_doses

Revision ID: p1a2b3c4d5e6
Revises: 
Create Date: 2026-08-17

"""
from alembic import op
import sqlalchemy as sa

revision = "p1a2b3c4d5e6"
down_revision = None  # set to your current head if needed
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE medication_course_doses "
        "ADD COLUMN IF NOT EXISTS patient_reminded BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE medication_course_doses DROP COLUMN IF EXISTS patient_reminded"
    )
