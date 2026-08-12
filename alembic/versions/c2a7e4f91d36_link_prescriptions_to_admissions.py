"""link_prescriptions_to_admissions

Revision ID: c2a7e4f91d36
Revises: 80485849b13b
Create Date: 2026-08-04 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2a7e4f91d36'
down_revision: Union[str, Sequence[str], None] = '80485849b13b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # A prescription can now come from either an OPD appointment or an
    # IPD ward round (admission) — appointment_id becomes optional and
    # admission_id is added. This is what lets the Pharmacist see
    # medicines ordered for admitted patients, not just walk-ins.
    op.alter_column(
        'prescriptions',
        'appointment_id',
        existing_type=sa.Integer(),
        nullable=True,
    )

    op.add_column(
        'prescriptions',
        sa.Column('admission_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_prescriptions_admission_id',
        'prescriptions',
        'admissions',
        ['admission_id'],
        ['id'],
    )

    op.create_check_constraint(
        'ck_prescription_has_source',
        'prescriptions',
        'appointment_id IS NOT NULL OR admission_id IS NOT NULL',
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ck_prescription_has_source', 'prescriptions', type_='check',
    )
    op.drop_constraint(
        'fk_prescriptions_admission_id', 'prescriptions', type_='foreignkey',
    )
    op.drop_column('prescriptions', 'admission_id')
    op.alter_column(
        'prescriptions',
        'appointment_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
    # ### end Alembic commands ###
