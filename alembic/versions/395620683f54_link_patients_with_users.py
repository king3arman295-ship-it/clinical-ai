"""link patients with users

Revision ID: 395620683f54
Revises: 9e2c7bc8a382
Create Date: 2026-07-16 09:25:58.702210

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "395620683f54"
down_revision: Union[str, Sequence[str], None] = "9e2c7bc8a382"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.
    """

    # -----------------------------
    # Add user_id (nullable for now)
    # -----------------------------
    op.add_column(
        "patients",
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # -----------------------------
    # Foreign Key
    # -----------------------------
    op.create_foreign_key(
        "fk_patients_user",
        "patients",
        "users",
        ["user_id"],
        ["id"],
    )

    # -----------------------------
    # Unique Constraint
    # -----------------------------
    op.create_unique_constraint(
        "uq_patients_user_id",
        "patients",
        ["user_id"],
    )


def downgrade() -> None:
    """
    Downgrade schema.
    """

    op.drop_constraint(
        "uq_patients_user_id",
        "patients",
        type_="unique",
    )

    op.drop_constraint(
        "fk_patients_user",
        "patients",
        type_="foreignkey",
    )

    op.drop_column(
        "patients",
        "user_id",
    )