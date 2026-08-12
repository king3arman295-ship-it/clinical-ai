"""add_laboratory_tables

Revision ID: d4e8f1a2b3c5
Revises: c2a7e4f91d36
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e8f1a2b3c5'
down_revision: Union[str, Sequence[str], None] = 'c2a7e4f91d36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lab_tests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('sample_type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('normal_range_min', sa.Float(), nullable=True),
        sa.Column('normal_range_max', sa.Float(), nullable=True),
        sa.Column('normal_range_text', sa.String(length=200), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('turnaround_hours', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_lab_tests_id'), 'lab_tests', ['id'], unique=False)

    op.create_table(
        'lab_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('ordered_by_doctor_id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=True),
        sa.Column('admission_id', sa.Integer(), nullable=True),
        sa.Column('prescription_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('clinical_notes', sa.Text(), nullable=True),
        sa.Column('sample_collected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sample_collected_by', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reported_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['admission_id'], ['admissions.id'], ),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
        sa.ForeignKeyConstraint(['ordered_by_doctor_id'], ['doctors.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
        sa.ForeignKeyConstraint(['prescription_id'], ['prescriptions.id'], ),
        sa.ForeignKeyConstraint(['reported_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['sample_collected_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_lab_orders_id'), 'lab_orders', ['id'], unique=False)

    op.create_table(
        'lab_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lab_order_id', sa.Integer(), nullable=False),
        sa.Column('lab_test_id', sa.Integer(), nullable=False),
        sa.Column('value_numeric', sa.Float(), nullable=True),
        sa.Column('value_text', sa.String(length=500), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('is_abnormal', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('entered_by', sa.Integer(), nullable=True),
        sa.Column('entered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['entered_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['lab_order_id'], ['lab_orders.id'], ),
        sa.ForeignKeyConstraint(['lab_test_id'], ['lab_tests.id'], ),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_lab_results_id'), 'lab_results', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lab_results_id'), table_name='lab_results')
    op.drop_table('lab_results')
    op.drop_index(op.f('ix_lab_orders_id'), table_name='lab_orders')
    op.drop_table('lab_orders')
    op.drop_index(op.f('ix_lab_tests_id'), table_name='lab_tests')
    op.drop_table('lab_tests')
