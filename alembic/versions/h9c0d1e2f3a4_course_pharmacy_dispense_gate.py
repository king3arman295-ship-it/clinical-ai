"""course_pharmacy_dispense_gate

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2026-08-06

Hospital flow: course items linked to pharmacy orders; nurse can give
only after pharmacy has dispensed the ward stock.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h9c0d1e2f3a4"
down_revision: Union[str, None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "medication_course_items",
        sa.Column("pharmacy_order_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_course_item_pharmacy_order",
        "medication_course_items",
        "pharmacy_orders",
        ["pharmacy_order_id"],
        ["id"],
    )

    op.add_column(
        "pharmacy_orders",
        sa.Column("source", sa.String(length=30), nullable=False, server_default="prescription"),
    )
    op.add_column(
        "pharmacy_orders",
        sa.Column("course_item_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "pharmacy_orders",
        sa.Column("form", sa.String(length=30), nullable=True),
    )
    op.create_foreign_key(
        "fk_pharmacy_order_course_item",
        "pharmacy_orders",
        "medication_course_items",
        ["course_item_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_pharmacy_order_course_item", "pharmacy_orders", type_="foreignkey")
    op.drop_column("pharmacy_orders", "form")
    op.drop_column("pharmacy_orders", "course_item_id")
    op.drop_column("pharmacy_orders", "source")
    op.drop_constraint("fk_course_item_pharmacy_order", "medication_course_items", type_="foreignkey")
    op.drop_column("medication_course_items", "pharmacy_order_id")
