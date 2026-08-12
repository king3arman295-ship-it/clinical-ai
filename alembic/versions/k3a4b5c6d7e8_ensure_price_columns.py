"""ensure_price_columns

Revision ID: k3a4b5c6d7e8
Revises: k2f3a4b5c6d7
Create Date: 2026-08-10

Ensure wards.daily_rate and medicines.unit_price columns exist and are writable.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "k3a4b5c6d7e8"
down_revision: Union[str, None] = "k2f3a4b5c6d7"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("wards", "daily_rate"):
        op.add_column(
            "wards",
            sa.Column("daily_rate", sa.Float(), nullable=False, server_default="2000"),
        )
    if not _has_column("medicines", "unit_price"):
        op.add_column(
            "medicines",
            sa.Column("unit_price", sa.Float(), nullable=False, server_default="50"),
        )


def downgrade() -> None:
    pass
