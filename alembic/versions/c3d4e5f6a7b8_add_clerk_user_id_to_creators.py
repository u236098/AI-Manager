"""Add clerk_user_id to creators

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-21 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("creators", sa.Column("clerk_user_id", sa.String(200), nullable=True))
    op.create_index("ix_creators_clerk_user_id", "creators", ["clerk_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_creators_clerk_user_id", table_name="creators")
    op.drop_column("creators", "clerk_user_id")
