"""add missing fcm_token to patients and doctors

app/models/patient.py and app/models/doctor.py both declare an
fcm_token column, but only users.fcm_token was ever created by a
migration (31bc1b7802f6 / f863772667f7). patients.fcm_token and
doctors.fcm_token were never added, so any query selecting a full
Patient or Doctor row (e.g. GET /doctors/) fails with UndefinedColumn.

Revision ID: m7e8f9a0b1c2
Revises: l6d7e8f9a0b1
Create Date: 2026-08-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m7e8f9a0b1c2"
down_revision: Union[str, None] = "l6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "patients",
        sa.Column("fcm_token", sa.String(), nullable=True),
    )
    op.add_column(
        "doctors",
        sa.Column("fcm_token", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("doctors", "fcm_token")
    op.drop_column("patients", "fcm_token")