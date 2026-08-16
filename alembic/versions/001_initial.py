"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rules",
        sa.Column("rule_id", sa.String(64), primary_key=True),
        sa.Column("keyword", sa.String(256), nullable=False),
        sa.Column("keyword_normalized", sa.String(256), nullable=False),
        sa.Column("dm_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rules_keyword_normalized", "rules", ["keyword_normalized"])

    op.create_table(
        "webhook_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "deleted_comments",
        sa.Column("comment_id", sa.String(128), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "outbound_dms",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("rule_id", sa.String(64), sa.ForeignKey("rules.rule_id"), nullable=False),
        sa.Column("recipient_user_id", sa.String(128), nullable=False),
        sa.Column("comment_id", sa.String(128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("dm_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("rule_id", "recipient_user_id", name="uq_dm_rule_user"),
    )
    op.create_index("ix_outbound_dms_rule_id", "outbound_dms", ["rule_id"])
    op.create_index("ix_outbound_dms_recipient_user_id", "outbound_dms", ["recipient_user_id"])
    op.create_index("ix_outbound_dms_comment_id", "outbound_dms", ["comment_id"])
    op.create_index("ix_outbound_dms_dm_id", "outbound_dms", ["dm_id"])
    op.create_index("ix_outbound_dms_status", "outbound_dms", ["status"])

    op.create_table(
        "duplicate_blocks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("recipient_user_id", sa.String(128), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("duplicate_blocks")
    op.drop_table("outbound_dms")
    op.drop_table("deleted_comments")
    op.drop_table("webhook_events")
    op.drop_table("rules")
