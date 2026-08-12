"""add_pharmacy_tables

Revision ID: 80485849b13b
Revises: 6b62fb60d1a8
Create Date: 2026-08-04 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80485849b13b'
down_revision: Union[str, Sequence[str], None] = '6b62fb60d1a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### Pharmacy Department ###

    op.create_table(
        'medicines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('form', sa.String(length=20), nullable=False),
        sa.Column('unit', sa.String(length=30), nullable=False),
        sa.Column('stock_qty', sa.Integer(), nullable=False),
        sa.Column('reorder_threshold', sa.Integer(), nullable=False),
        sa.Column('batch_number', sa.String(length=100), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_medicines_id'), 'medicines', ['id'], unique=False)

    op.create_table(
        'pharmacy_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prescription_item_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('medicine_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('dispensed_by', sa.Integer(), nullable=True),
        sa.Column('dispensed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['dispensed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['medicine_id'], ['medicines.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
        sa.ForeignKeyConstraint(['prescription_item_id'], ['prescription_items.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pharmacy_orders_id'), 'pharmacy_orders', ['id'], unique=False)

    op.create_table(
        'medication_administrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admission_id', sa.Integer(), nullable=False),
        sa.Column('medicine_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('given_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('given_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['admission_id'], ['admissions.id'], ),
        sa.ForeignKeyConstraint(['given_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['medicine_id'], ['medicines.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_medication_administrations_id'), 'medication_administrations', ['id'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_medication_administrations_id'), table_name='medication_administrations')
    op.drop_table('medication_administrations')

    op.drop_index(op.f('ix_pharmacy_orders_id'), table_name='pharmacy_orders')
    op.drop_table('pharmacy_orders')

    op.drop_index(op.f('ix_medicines_id'), table_name='medicines')
    op.drop_table('medicines')
    # ### end Alembic commands ###
