"""Add automatic class-level peer-assessment gates.

Revision ID: 0004_class_peer_gate
Revises: 0003_v15_products_peer_social
Create Date: 2026-11-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0004_class_peer_gate"
down_revision: Union[str, None] = "0003_v15_products_peer_social"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _tables()
    if "class_peer_gates" not in existing:
        op.create_table(
            "class_peer_gates",
            sa.Column("class_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="collecting"),
            sa.Column("membership_frozen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("peer_opened_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("entered_count_at_open", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("t2_ended_count_at_open", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("valid_work_count_at_open", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("batch_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
            sa.ForeignKeyConstraint(["batch_id"], ["peer_batches.id"]),
            sa.PrimaryKeyConstraint("class_id"),
        )

    if "class_peer_gate_events" not in existing:
        op.create_table(
            "class_peer_gate_events",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("class_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("counts_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("peer_batch_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_class_peer_gate_events_class_id", "class_peer_gate_events", ["class_id"])

    # Backfill one gate row per existing class. Existing v1.5 batches are
    # treated as legacy-open so no current peer session is blocked.
    op.execute(
        sa.text(
            """
            INSERT INTO class_peer_gates
                (class_id, status, entered_count_at_open, t2_ended_count_at_open,
                 valid_work_count_at_open, created_at, updated_at)
            SELECT id, 'collecting', 0, 0, 0, now(), now()
            FROM classes
            ON CONFLICT (class_id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE class_peer_gates g
            SET status = 'open',
                membership_frozen_at = b.created_at,
                peer_opened_at = b.created_at,
                batch_id = b.id,
                updated_at = now()
            FROM (
                SELECT DISTINCT ON (class_id) id, class_id, created_at
                FROM peer_batches
                WHERE status <> 'superseded'
                ORDER BY class_id, created_at DESC
            ) b
            WHERE b.class_id = g.class_id
            """
        )
    )
    indexes = {item.get("name") for item in inspect(op.get_bind()).get_indexes("peer_batches")}
    if "uq_peer_batch_active" not in indexes:
        op.create_index(
            "uq_peer_batch_active",
            "peer_batches",
            ["class_id"],
            unique=True,
            postgresql_where=sa.text("status <> 'superseded'"),
        )


def downgrade() -> None:
    existing = _tables()
    indexes = {item.get("name") for item in inspect(op.get_bind()).get_indexes("peer_batches")}
    if "uq_peer_batch_active" in indexes:
        op.drop_index("uq_peer_batch_active", table_name="peer_batches")
    if "class_peer_gate_events" in existing:
        op.drop_table("class_peer_gate_events")
    if "class_peer_gates" in existing:
        op.drop_table("class_peer_gates")
