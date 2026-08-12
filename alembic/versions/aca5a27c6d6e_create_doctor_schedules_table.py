"""create doctor schedules table"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision = "aca5a27c6d6e"
down_revision = "99993d81a84f"
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "doctor_schedules",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "doctor_id",
            sa.Integer(),
            sa.ForeignKey("doctors.id"),
            nullable=False,
        ),

        sa.Column(
            "day_of_week",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "start_time",
            sa.Time(),
            nullable=False,
        ),

        sa.Column(
            "end_time",
            sa.Time(),
            nullable=False,
        ),

        sa.Column(
            "is_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade():

    op.drop_table("doctor_schedules")