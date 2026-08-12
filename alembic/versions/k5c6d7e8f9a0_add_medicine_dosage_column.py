"""add_medicine_dosage_column

Revision ID: k5c6d7e8f9a0
Revises: k4b5c6d7e8f9
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "k5c6d7e8f9a0"
down_revision = "k4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("medicines")} if "medicines" in insp.get_table_names() else set()
    if "dosage" not in cols:
        op.add_column("medicines", sa.Column("dosage", sa.String(length=100), nullable=True))
    existing_constraints = {c["name"] for c in insp.get_unique_constraints("medicines")}
    if "medicines_name_key" in existing_constraints:
        op.drop_constraint("medicines_name_key", "medicines", type_="unique")


def downgrade() -> None:
    pass
