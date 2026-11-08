"""Persist the HLSF prompt version per run for v1.9.

Revision ID: 0016_hlsf_prompt_version
Revises: 0015_beta_peer_snapshots
Create Date: 2026-11-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0016_hlsf_prompt_version"
down_revision: Union[str, None] = "0015_beta_peer_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns("runs")}


def upgrade() -> None:
    if "hlsf_prompt_version" not in _columns():
        op.add_column(
            "runs",
            sa.Column("hlsf_prompt_version", sa.String(length=64), nullable=True),
        )
    # Existing runs intentionally stay NULL so the resolver keeps v1.7/v1.8.


def downgrade() -> None:
    if "hlsf_prompt_version" in _columns():
        op.drop_column("runs", "hlsf_prompt_version")
