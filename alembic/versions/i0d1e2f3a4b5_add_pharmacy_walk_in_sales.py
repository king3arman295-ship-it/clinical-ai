"""add_pharmacy_walk_in_sales

Revision ID: i0d1e2f3a4b5
Revises: h9c0d1e2f3a4
Create Date: 2026-08-09

OTC / counter walk-in sales — pharmacist dispenses without a doctor order.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i0d1e2f3a4b5"
down_revision: Union[str, None] = "h9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pharmacy_walk_in_sales",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sold_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_pharmacy_walk_in_sales_id", "pharmacy_walk_in_sales", ["id"])


def downgrade() -> None:
    op.drop_index("ix_pharmacy_walk_in_sales_id", table_name="pharmacy_walk_in_sales")
    op.drop_table("pharmacy_walk_in_sales")
