"""Add notification_sent to appointments

Revision ID: a499cadf9478
Revises: 31bc1b7802f6
Create Date: 2026-07-21 05:22:38.408285

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a499cadf9478"
down_revision: Union[str, Sequence[str], None] = "31bc1b7802f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "appointments",
        sa.Column(
            "notification_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Remove default after existing rows are updated
    op.alter_column(
        "appointments",
        "notification_sent",
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "appointments",
        "notification_sent",
    )