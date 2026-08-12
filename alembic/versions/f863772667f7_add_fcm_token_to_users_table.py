"""add_fcm_token_to_users_table

Revision ID: f863772667f7
Revises: a499cadf9478
Create Date: 2026-07-21 23:19:32.509611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f863772667f7'
down_revision: Union[str, Sequence[str], None] = 'a499cadf9478'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("fcm_token", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        "users",
        "fcm_token",
    )

