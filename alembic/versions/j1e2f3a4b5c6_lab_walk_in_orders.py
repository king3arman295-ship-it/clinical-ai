"""lab_walk_in_orders

Revision ID: j1e2f3a4b5c6
Revises: i0d1e2f3a4b5
Create Date: 2026-08-09

Allow lab technicians to create walk-in lab orders without a doctor.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j1e2f3a4b5c6"
down_revision: Union[str, None] = "i0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("lab_orders", "patient_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "lab_orders", "ordered_by_doctor_id", existing_type=sa.Integer(), nullable=True
    )
    op.add_column(
        "lab_orders",
        sa.Column(
            "order_source",
            sa.String(length=30),
            nullable=False,
            server_default="doctor",
        ),
    )
    op.add_column(
        "lab_orders",
        sa.Column("customer_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "lab_orders",
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lab_orders", "customer_phone")
    op.drop_column("lab_orders", "customer_name")
    op.drop_column("lab_orders", "order_source")
    op.alter_column(
        "lab_orders", "ordered_by_doctor_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column("lab_orders", "patient_id", existing_type=sa.Integer(), nullable=False)
