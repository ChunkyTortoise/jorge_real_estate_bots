"""Add first-class canonical conversation fields.

Revision ID: 20260306_000003
Revises: 20260303_000002
Create Date: 2026-03-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260306_000003"
down_revision = "20260303_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("mode", sa.String(length=50), nullable=True))
    op.add_column("conversations", sa.Column("mode_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("conversations", sa.Column("status", sa.String(length=50), nullable=True))
    op.add_column("conversations", sa.Column("handoff_reason", sa.String(length=100), nullable=True))
    op.add_column("conversations", sa.Column("human_takeover", sa.Boolean(), nullable=True))
    op.add_column("conversations", sa.Column("bilingual_required", sa.Boolean(), nullable=True))
    op.add_column("conversations", sa.Column("message_suppression_reason", sa.String(length=100), nullable=True))
    op.add_column(
        "conversations",
        sa.Column(
            "qualification_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("conversations", sa.Column("next_recommended_action", sa.String(length=255), nullable=True))
    op.add_column("conversations", sa.Column("crm_sync_status", sa.String(length=50), nullable=True))
    op.add_column("conversations", sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("last_outbound_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_conversations_mode", "conversations", ["mode"], unique=False)
    op.create_index("ix_conversations_status", "conversations", ["status"], unique=False)

    op.execute(
        """
        UPDATE conversations
        SET
            mode = COALESCE(metadata_json->>'mode', CASE
                WHEN bot_type = 'seller' THEN 'seller'
                WHEN bot_type = 'buyer' THEN 'buyer'
                ELSE 'lead_intake'
            END),
            mode_version = COALESCE(CASE WHEN metadata_json->>'mode_version' ~ E'^\\d+$' THEN (metadata_json->>'mode_version')::integer ELSE 1 END, 1),
            status = COALESCE(metadata_json->>'status', CASE
                WHEN stage = 'STALLED' THEN 'stalled'
                WHEN is_qualified = true OR stage = 'QUALIFIED' THEN 'qualified'
                ELSE 'active'
            END),
            handoff_reason = metadata_json->>'handoff_reason',
            human_takeover = COALESCE(NULLIF(metadata_json->>'human_takeover', '')::boolean, false),
            bilingual_required = COALESCE(NULLIF(metadata_json->>'bilingual_required', '')::boolean, false),
            message_suppression_reason = metadata_json->>'message_suppression_reason',
            qualification_summary = COALESCE(metadata_json->'qualification_summary', '{}'::jsonb),
            next_recommended_action = metadata_json->>'next_recommended_action',
            crm_sync_status = COALESCE(metadata_json->>'crm_sync_status', 'historical'),
            last_inbound_at = NULLIF(metadata_json->>'last_inbound_at', '')::timestamptz,
            last_outbound_at = NULLIF(metadata_json->>'last_outbound_at', '')::timestamptz
        """
    )

    # Set persistent server_default for crm_sync_status so raw SQL inserts get "pending".
    op.alter_column("conversations", "crm_sync_status", server_default="pending")


def downgrade() -> None:
    op.execute(
        """
        UPDATE conversations
        SET metadata_json = metadata_json || jsonb_build_object(
            'mode', mode,
            'mode_version', mode_version,
            'status', status,
            'handoff_reason', handoff_reason,
            'human_takeover', human_takeover,
            'bilingual_required', bilingual_required,
            'message_suppression_reason', message_suppression_reason,
            'qualification_summary', qualification_summary,
            'next_recommended_action', next_recommended_action,
            'crm_sync_status', crm_sync_status,
            'last_inbound_at', last_inbound_at,
            'last_outbound_at', last_outbound_at
        )
        WHERE mode IS NOT NULL OR status IS NOT NULL
        """
    )

    op.drop_index("ix_conversations_status", table_name="conversations")
    op.drop_index("ix_conversations_mode", table_name="conversations")

    op.drop_column("conversations", "last_outbound_at")
    op.drop_column("conversations", "last_inbound_at")
    op.drop_column("conversations", "crm_sync_status")
    op.drop_column("conversations", "next_recommended_action")
    op.drop_column("conversations", "qualification_summary")
    op.drop_column("conversations", "message_suppression_reason")
    op.drop_column("conversations", "bilingual_required")
    op.drop_column("conversations", "human_takeover")
    op.drop_column("conversations", "handoff_reason")
    op.drop_column("conversations", "status")
    op.drop_column("conversations", "mode_version")
    op.drop_column("conversations", "mode")
