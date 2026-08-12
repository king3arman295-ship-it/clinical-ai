"""Add video consultation fields to appointments

Revision ID: f1b76df103f9
Revises: 1818b66c7852
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1b76df103f9"
down_revision: Union[str, Sequence[str], None] = "1818b66c7852"
branch_labels = None
depends_on = None


# ---------------------------------------------------------
# ENUMS
# ---------------------------------------------------------

appointment_type_enum = sa.Enum(
    "physical",
    "video",
    "home",
    name="appointment_type_enum",
)

meeting_status_enum = sa.Enum(
    "scheduled",
    "waiting",
    "live",
    "completed",
    "cancelled",
    name="meeting_status_enum",
)


def upgrade():

    bind = op.get_bind()

    # Create ENUM types first
    appointment_type_enum.create(bind, checkfirst=True)
    meeting_status_enum.create(bind, checkfirst=True)

    # -------------------------------------------------

    op.add_column(
        "appointments",
        sa.Column(
            "appointment_type",
            appointment_type_enum,
            nullable=False,
            server_default="physical",
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "video_channel",
            sa.String(150),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "meeting_status",
            meeting_status_enum,
            nullable=False,
            server_default="scheduled",
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "meeting_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "meeting_ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "call_duration",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade():

    op.drop_column("appointments", "call_duration")
    op.drop_column("appointments", "meeting_ended_at")
    op.drop_column("appointments", "meeting_started_at")
    op.drop_column("appointments", "meeting_status")
    op.drop_column("appointments", "video_channel")
    op.drop_column("appointments", "appointment_type")

    bind = op.get_bind()

    meeting_status_enum.drop(bind, checkfirst=True)
    appointment_type_enum.drop(bind, checkfirst=True)