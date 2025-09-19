"""Add categories and category_feed association table

Revision ID: 002
Revises: 001
Create Date: 2025-01-19 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create categories table
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create indexes for categories
    op.create_index("ix_categories_name", "categories", ["name"], unique=False)
    op.create_index("ix_categories_order", "categories", ["order"], unique=False)

    # Create category_feed association table
    op.create_table(
        "category_feed",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.String(), server_default="now()", nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("category_id", "feed_id"),
    )

    # Create indexes for category_feed association table
    op.create_index(
        "ix_category_feed_category_id", "category_feed", ["category_id"], unique=False
    )
    op.create_index(
        "ix_category_feed_feed_id", "category_feed", ["feed_id"], unique=False
    )


def downgrade() -> None:
    # Drop indexes for category_feed
    op.drop_index("ix_category_feed_feed_id", table_name="category_feed")
    op.drop_index("ix_category_feed_category_id", table_name="category_feed")

    # Drop category_feed table
    op.drop_table("category_feed")

    # Drop indexes for categories
    op.drop_index("ix_categories_order", table_name="categories")
    op.drop_index("ix_categories_name", table_name="categories")

    # Drop categories table
    op.drop_table("categories")
