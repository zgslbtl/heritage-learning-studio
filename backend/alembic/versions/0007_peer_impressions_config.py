"""Peer exposure impressions and allocation config.

Revision ID: 0007_peer_impressions_config
Revises: 0006_formal_content_forms_media
Create Date: 2026-11-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0007_peer_impressions_config"
down_revision: Union[str, None] = "0006_formal_content_forms_media"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "config_json" not in _columns("peer_batches"):
        op.add_column(
            "peer_batches",
            sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )
    if "peer_impressions" not in _tables():
        op.create_table(
            "peer_impressions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("assignment_id", sa.Uuid(), nullable=False),
            sa.Column("batch_id", sa.Uuid(), nullable=False),
            sa.Column("reviewer_run_id", sa.Uuid(), nullable=False),
            sa.Column("work_id", sa.BigInteger(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("shown_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("viewed_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["assignment_id"], ["peer_assignments.id"]),
            sa.ForeignKeyConstraint(["batch_id"], ["peer_batches.id"]),
            sa.ForeignKeyConstraint(["reviewer_run_id"], ["runs.id"]),
            sa.ForeignKeyConstraint(["work_id"], ["work_revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("assignment_id"),
        )
        op.create_index("ix_peer_impressions_assignment_id", "peer_impressions", ["assignment_id"], unique=True)
        op.create_index("ix_peer_impressions_batch_id", "peer_impressions", ["batch_id"])
        op.create_index("ix_peer_impressions_reviewer_run_id", "peer_impressions", ["reviewer_run_id"])
        op.create_index("ix_peer_impressions_work_id", "peer_impressions", ["work_id"])


def downgrade() -> None:
    if "peer_impressions" in _tables():
        op.drop_table("peer_impressions")
    if "config_json" in _columns("peer_batches"):
        op.drop_column("peer_batches", "config_json")
