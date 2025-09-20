"""Add hide_read_items to user_settings

Revision ID: 004
Revises: 003
Create Date: 2025-01-27 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add hide_read_items column to user_settings table
    op.add_column(
        "user_settings",
        sa.Column(
            "hide_read_items", sa.Boolean(), nullable=False, server_default="false"
        ),
    )


def downgrade() -> None:
    # Remove hide_read_items column from user_settings table
    op.drop_column("user_settings", "hide_read_items")
