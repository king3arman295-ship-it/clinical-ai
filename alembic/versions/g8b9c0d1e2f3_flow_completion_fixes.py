"""flow_completion_fixes — encounter billing, qty, bill links

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prescription_items",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "pharmacy_orders",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "pharmacy_orders",
        sa.Column("bill_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pharmacy_orders_bill_id",
        "pharmacy_orders",
        "bills",
        ["bill_id"],
        ["id"],
    )

    op.add_column("bills", sa.Column("appointment_id", sa.Integer(), nullable=True))
    op.add_column("bills", sa.Column("admission_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_bills_appointment_id", "bills", "appointments", ["appointment_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_bills_admission_id", "bills", "admissions", ["admission_id"], ["id"]
    )

    op.add_column(
        "lab_orders",
        sa.Column("bill_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_lab_orders_bill_id", "lab_orders", "bills", ["bill_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_lab_orders_bill_id", "lab_orders", type_="foreignkey")
    op.drop_column("lab_orders", "bill_id")
    op.drop_constraint("fk_bills_admission_id", "bills", type_="foreignkey")
    op.drop_constraint("fk_bills_appointment_id", "bills", type_="foreignkey")
    op.drop_column("bills", "admission_id")
    op.drop_column("bills", "appointment_id")
    op.drop_constraint("fk_pharmacy_orders_bill_id", "pharmacy_orders", type_="foreignkey")
    op.drop_column("pharmacy_orders", "bill_id")
    op.drop_column("pharmacy_orders", "quantity")
    op.drop_column("prescription_items", "quantity")
