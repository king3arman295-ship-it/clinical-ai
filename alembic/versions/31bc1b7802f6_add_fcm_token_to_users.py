"""Add fcm token to users

Revision ID: 31bc1b7802f6
Revises: f1b76df103f9
Create Date: 2026-07-21 03:36:46.423418
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "31bc1b7802f6"
down_revision: Union[str, Sequence[str], None] = "f1b76df103f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("fcm_token", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column(
        "users",
        "fcm_token",
    )