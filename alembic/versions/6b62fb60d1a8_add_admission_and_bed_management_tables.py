"""add_admission_and_bed_management_tables

Revision ID: 6b62fb60d1a8
Revises: b7d3a1c9e4f2
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b62fb60d1a8'
down_revision: Union[str, Sequence[str], None] = 'b7d3a1c9e4f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### Admission Department (IPD / Bed Management) ###

    op.create_table(
        'wards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('total_beds', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_wards_id'), 'wards', ['id'], unique=False)

    op.create_table(
        'beds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ward_id', sa.Integer(), nullable=False),
        sa.Column('bed_number', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ward_id', 'bed_number', name='uq_bed_ward_number'),
    )
    op.create_index(op.f('ix_beds_id'), 'beds', ['id'], unique=False)

    op.create_table(
        'admissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('requesting_doctor_id', sa.Integer(), nullable=False),
        sa.Column('admitting_doctor_id', sa.Integer(), nullable=True),
        sa.Column('bed_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('urgency', sa.String(length=20), nullable=False),
        sa.Column('preferred_ward_type', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('condition_flag', sa.String(length=20), nullable=True),
        sa.Column('discharge_summary', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('admitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('discharged_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['admitting_doctor_id'], ['doctors.id'], ),
        sa.ForeignKeyConstraint(['bed_id'], ['beds.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
        sa.ForeignKeyConstraint(['requesting_doctor_id'], ['doctors.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_admissions_id'), 'admissions', ['id'], unique=False)

    op.create_table(
        'admission_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admission_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('vitals', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['admission_id'], ['admissions.id'], ),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_admission_notes_id'), 'admission_notes', ['id'], unique=False)

    # Patient's overall OPD/IPD status — flipped by AdmissionService when
    # a bed is allocated / the patient is discharged.
    op.add_column(
        'patients',
        sa.Column(
            'care_type',
            sa.String(length=10),
            nullable=False,
            server_default='opd',
        ),
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('patients', 'care_type')

    op.drop_index(op.f('ix_admission_notes_id'), table_name='admission_notes')
    op.drop_table('admission_notes')

    op.drop_index(op.f('ix_admissions_id'), table_name='admissions')
    op.drop_table('admissions')

    op.drop_index(op.f('ix_beds_id'), table_name='beds')
    op.drop_table('beds')

    op.drop_index(op.f('ix_wards_id'), table_name='wards')
    op.drop_table('wards')
    # ### end Alembic commands ###
