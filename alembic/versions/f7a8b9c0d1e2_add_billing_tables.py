"""add_billing_tables

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Optional unit price on pharmacy stock for bill line items
    op.add_column(
        "medicines",
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="50"),
    )
    # Daily bed rate by ward
    op.add_column(
        "wards",
        sa.Column("daily_rate", sa.Float(), nullable=False, server_default="2000"),
    )

    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bill_number", sa.String(length=40), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("patient_name", sa.String(length=150), nullable=False),
        sa.Column("patient_phone", sa.String(length=30), nullable=True),
        sa.Column("patient_email", sa.String(length=150), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("subtotal", sa.Float(), nullable=False),
        sa.Column("discount", sa.Float(), nullable=False),
        sa.Column("tax", sa.Float(), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.String(length=40), nullable=True),
        sa.Column("issued_by", sa.Integer(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bill_number"),
    )
    op.create_index(op.f("ix_bills_id"), "bills", ["id"], unique=False)
    op.create_index(op.f("ix_bills_bill_number"), "bills", ["bill_number"], unique=False)
    op.create_index(op.f("ix_bills_patient_id"), "bills", ["patient_id"], unique=False)

    op.create_table(
        "bill_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bill_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("reference_type", sa.String(length=40), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bill_items_id"), "bill_items", ["id"], unique=False)
    op.create_index(op.f("ix_bill_items_bill_id"), "bill_items", ["bill_id"], unique=False)

    # Seed sensible daily rates by ward type (already created rows)
    op.execute(
        """
        UPDATE wards SET daily_rate = CASE lower(type)
            WHEN 'icu' THEN 8000
            WHEN 'private' THEN 5000
            WHEN 'pediatric' THEN 2500
            ELSE 2000
        END
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_bill_items_bill_id"), table_name="bill_items")
    op.drop_index(op.f("ix_bill_items_id"), table_name="bill_items")
    op.drop_table("bill_items")
    op.drop_index(op.f("ix_bills_patient_id"), table_name="bills")
    op.drop_index(op.f("ix_bills_bill_number"), table_name="bills")
    op.drop_index(op.f("ix_bills_id"), table_name="bills")
    op.drop_table("bills")
    op.drop_column("wards", "daily_rate")
    op.drop_column("medicines", "unit_price")
