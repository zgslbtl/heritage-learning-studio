"""Widen AI prompt version for v1.6 pilot identifiers.

Revision ID: 0010_widen_prompt_version
Revises: 0009_image_prompt_selection
Create Date: 2026-11-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0010_widen_prompt_version"
down_revision: Union[str, None] = "0009_image_prompt_selection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"]: column for column in inspect(op.get_bind()).get_columns("ai_calls")}
    current = columns.get("prompt_version")
    if current is not None and getattr(current.get("type"), "length", 0) < 64:
        op.alter_column(
            "ai_calls",
            "prompt_version",
            existing_type=sa.String(length=current.get("type").length or 24),
            type_=sa.String(length=64),
            existing_nullable=False,
        )


def downgrade() -> None:
    op.alter_column(
        "ai_calls",
        "prompt_version",
        existing_type=sa.String(length=64),
        type_=sa.String(length=24),
        existing_nullable=False,
    )
