"""add nurse module tables

Revision ID: e5f6a7b8c9d0
Revises: d4e8f1a2b3c5
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e8f1a2b3c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nurse_bed_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nurse_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bed_id", sa.Integer(), sa.ForeignKey("beds.id"), nullable=False),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("nurse_user_id", "bed_id", name="uq_nurse_bed"),
    )
    op.create_index("ix_nurse_bed_assignments_nurse_user_id", "nurse_bed_assignments", ["nurse_user_id"])
    op.create_index("ix_nurse_bed_assignments_bed_id", "nurse_bed_assignments", ["bed_id"])

    op.create_table(
        "medication_courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False),
        sa.Column("ordered_by_doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("clinical_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_medication_courses_admission_id", "medication_courses", ["admission_id"])

    op.create_table(
        "medication_course_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("medication_courses.id"), nullable=False),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id"), nullable=True),
        sa.Column("medicine_name", sa.String(200), nullable=False),
        sa.Column("route", sa.String(30), nullable=False, server_default="oral"),
        sa.Column("dosage", sa.String(100), nullable=False),
        sa.Column("frequency", sa.String(50), nullable=False, server_default="OD"),
        sa.Column("times_per_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schedule_times", sa.String(120), nullable=True),
        sa.Column("drip_rate", sa.String(100), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_medication_course_items_course_id", "medication_course_items", ["course_id"])

    op.create_table(
        "medication_course_doses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("medication_courses.id"), nullable=False),
        sa.Column("course_item_id", sa.Integer(), sa.ForeignKey("medication_course_items.id"), nullable=False),
        sa.Column("admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("scheduled_time", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("given_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("medication_administration_id", sa.Integer(), sa.ForeignKey("medication_administrations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_medication_course_doses_course_id", "medication_course_doses", ["course_id"])
    op.create_index("ix_medication_course_doses_item_id", "medication_course_doses", ["course_item_id"])
    op.create_index("ix_medication_course_doses_admission_id", "medication_course_doses", ["admission_id"])
    op.create_index("ix_medication_course_doses_date", "medication_course_doses", ["scheduled_date"])


def downgrade() -> None:
    op.drop_table("medication_course_doses")
    op.drop_table("medication_course_items")
    op.drop_table("medication_courses")
    op.drop_table("nurse_bed_assignments")
