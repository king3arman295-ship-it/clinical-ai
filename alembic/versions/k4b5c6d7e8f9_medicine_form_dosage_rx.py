"""medicine_form_dosage_rx

Revision ID: k4b5c6d7e8f9
Revises: k3a4b5c6d7e8
Create Date: 2026-08-10

Prescription form + medicine dosage for exact pharmacy matching.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "k4b5c6d7e8f9"
down_revision = "k3a4b5c6d7e8"
branch_labels = None
depends_on = None


def _cols(table):
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    med_cols = _cols("medicines")
    if "dosage" not in med_cols:
        op.add_column("medicines", sa.Column("dosage", sa.String(100), nullable=True))
    try:
        op.drop_constraint("medicines_name_key", "medicines", type_="unique")
    except Exception:
        pass
    pi_cols = _cols("prescription_items")
    if "form" not in pi_cols:
        op.add_column("prescription_items", sa.Column("form", sa.String(30), nullable=True))


def downgrade() -> None:
    pass
