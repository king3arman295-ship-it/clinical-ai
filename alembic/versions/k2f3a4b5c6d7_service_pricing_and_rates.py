"""service_pricing_and_rates

Revision ID: k2f3a4b5c6d7
Revises: j1e2f3a4b5c6
Create Date: 2026-08-10

Admin-managed service fees; ensure medicines.unit_price and wards.daily_rate exist.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "k2f3a4b5c6d7"
down_revision: Union[str, None] = "j1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_pricing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_service_pricing_key", "service_pricing", ["key"], unique=True)

    # Seed defaults (nursing + hospital service + consultation fallback)
    op.execute(
        """
        INSERT INTO service_pricing (key, label, amount, description) VALUES
        ('nursing_per_dose', 'Nursing fee per dose given', 150, 'Charged when nurse marks a course dose as given'),
        ('nursing_per_day', 'Nursing care per admission day', 500, 'Daily nursing charge for admitted patients'),
        ('hospital_service_fee', 'Hospital service / facility fee', 200, 'Optional facility fee applied per bill episode'),
        ('default_consultation_fee', 'Default consultation fee', 500, 'Used when doctor has no consultation_fee set')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_service_pricing_key", table_name="service_pricing")
    op.drop_table("service_pricing")
