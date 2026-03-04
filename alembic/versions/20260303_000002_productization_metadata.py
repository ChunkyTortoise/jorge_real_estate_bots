"""Add productization metadata tables.

Revision ID: 20260303_000002
Revises: 20260206_000001
Create Date: 2026-03-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260303_000002"
down_revision = "20260206_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "playbook_applications",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agency_id", sa.String(), nullable=False),
        sa.Column("playbook_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("applied_by", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("applied_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_playbook_applications_agency_id", "playbook_applications", ["agency_id"], unique=False)
    op.create_index(
        "ix_playbook_applications_agency_active",
        "playbook_applications",
        ["agency_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "roi_reports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agency_id", sa.String(length=255), nullable=True),
        sa.Column("date_from", sa.DateTime(), nullable=True),
        sa.Column("date_to", sa.DateTime(), nullable=True),
        sa.Column("format", sa.String(length=20), nullable=False, server_default=sa.text("'both'")),
        sa.Column("artifact_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("generated_by", sa.String(length=255), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roi_reports_agency_id", "roi_reports", ["agency_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_roi_reports_agency_id", table_name="roi_reports")
    op.drop_table("roi_reports")

    op.drop_index("ix_playbook_applications_agency_active", table_name="playbook_applications")
    op.drop_index("ix_playbook_applications_agency_id", table_name="playbook_applications")
    op.drop_table("playbook_applications")
