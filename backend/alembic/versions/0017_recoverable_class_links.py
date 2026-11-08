"""Retain recoverable class entry links for the administrator list.

Revision ID: 0017_recoverable_class_links
Revises: 0016_hlsf_prompt_version
Create Date: 2026-11-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_recoverable_class_links"
down_revision = "0016_hlsf_prompt_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("class_entry_links")}
    if "token_scheme" not in columns:
        op.add_column("class_entry_links", sa.Column("token_scheme", sa.String(32), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("class_entry_links")}
    if "token_scheme" in columns:
        op.drop_column("class_entry_links", "token_scheme")
