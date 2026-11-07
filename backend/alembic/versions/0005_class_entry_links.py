"""Add per-class entry links.

Revision ID: 0005_class_entry_links
Revises: 0004_class_peer_gate
Create Date: 2026-11-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0005_class_entry_links"
down_revision: Union[str, None] = "0004_class_peer_gate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "class_entry_links" in set(inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "class_entry_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_class_entry_links_class_id", "class_entry_links", ["class_id"])
    op.create_index("ix_class_entry_links_token_hash", "class_entry_links", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("class_entry_links")
