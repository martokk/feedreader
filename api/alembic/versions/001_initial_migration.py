"""Initial migration

Revision ID: 001
Revises:
Create Date: 2025-01-19 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create feeds table
    op.create_table(
        "feeds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.Integer(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("per_host_key", sa.String(length=256), nullable=False),
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
        sa.UniqueConstraint("url"),
    )
    op.create_index("ix_feeds_next_run_at", "feeds", ["next_run_at"], unique=False)
    op.create_index("ix_feeds_per_host_key", "feeds", ["per_host_key"], unique=False)

    # Create items table
    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guid", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["feeds.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feed_id", "guid", name="uq_items_feed_guid"),
    )
    op.create_index("ix_items_created_at", "items", ["created_at"], unique=False)
    op.create_index("ix_items_feed_id", "items", ["feed_id"], unique=False)
    op.create_index("ix_items_published_at", "items", ["published_at"], unique=False)

    # Create read_state table
    op.create_table(
        "read_state",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("starred", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
        ),
        sa.PrimaryKeyConstraint("item_id"),
    )

    # Create fetch_log table
    op.create_table(
        "fetch_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["feeds.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("fetch_log")
    op.drop_table("read_state")
    op.drop_index("ix_items_published_at", table_name="items")
    op.drop_index("ix_items_feed_id", table_name="items")
    op.drop_index("ix_items_created_at", table_name="items")
    op.drop_table("items")
    op.drop_index("ix_feeds_per_host_key", table_name="feeds")
    op.drop_index("ix_feeds_next_run_at", table_name="feeds")
    op.drop_table("feeds")
