"""create doctor schedules table

Revision ID: 1818b66c7852
Revises: aca5a27c6d6e
Create Date: 2026-07-19 23:24:16.808804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1818b66c7852'
down_revision: Union[str, Sequence[str], None] = 'aca5a27c6d6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    NOTE: this migration originally re-created 'doctor_schedules' from
    scratch, duplicating the table already created by revision
    aca5a27c6d6e (this migration's own down_revision). Running both
    back to back always crashed with "relation doctor_schedules already
    exists". The only column the earlier migration was missing is
    slot_duration (required by app.models.doctor_schedule.DoctorSchedule),
    so this migration now just adds that column instead of recreating
    the table.
    """
    op.add_column(
        'doctor_schedules',
        sa.Column('slot_duration', sa.Integer(), nullable=False, server_default='30'),
    )
    # Drop the server_default after backfilling existing rows so future
    # inserts must supply it explicitly, matching the model (default=30
    # is enforced at the ORM level, not the DB level).
    op.alter_column('doctor_schedules', 'slot_duration', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('doctor_schedules', 'slot_duration')
