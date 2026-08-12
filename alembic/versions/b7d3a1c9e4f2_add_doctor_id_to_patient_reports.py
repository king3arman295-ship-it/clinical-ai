"""add doctor_id to patient_reports

Revision ID: b7d3a1c9e4f2
Revises: 1a91588e162b
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d3a1c9e4f2'
down_revision: Union[str, Sequence[str], None] = '1a91588e162b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patient_reports', sa.Column('doctor_id', sa.Integer(), nullable=True))
    op.execute('''
        UPDATE patient_reports pr
        SET doctor_id = a.doctor_id
        FROM appointments a
        WHERE pr.appointment_id = a.id
    ''')
    op.create_foreign_key(None, 'patient_reports', 'doctors', ['doctor_id'], ['id'])
    op.create_index(op.f('ix_patient_reports_doctor_id'), 'patient_reports', ['doctor_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_patient_reports_doctor_id'), table_name='patient_reports')
    op.drop_constraint('patient_reports_doctor_id_fkey', 'patient_reports', type_='foreignkey')
    op.drop_column('patient_reports', 'doctor_id')
