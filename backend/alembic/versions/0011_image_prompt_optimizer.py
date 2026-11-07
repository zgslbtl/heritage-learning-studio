"""Image prompt optimizer and reference-image generation.

Revision ID: 0011_image_prompt_optimizer
Revises: 0010_widen_prompt_version
Create Date: 2026-11-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0011_image_prompt_optimizer"
down_revision: Union[str, None] = "0010_widen_prompt_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    ai_columns = _columns("ai_calls")
    if ai_columns:
        current = next(
            (
                column
                for column in inspect(op.get_bind()).get_columns("ai_calls")
                if column["name"] == "purpose"
            ),
            None,
        )
        if current is not None and getattr(current.get("type"), "length", 0) < 64:
            op.alter_column(
                "ai_calls",
                "purpose",
                existing_type=sa.String(length=current.get("type").length or 24),
                type_=sa.String(length=64),
                existing_nullable=False,
            )
    columns = _columns("image_jobs")
    if "source_prompt" not in columns:
        op.add_column(
            "image_jobs",
            sa.Column("source_prompt", sa.Text(), nullable=False, server_default=""),
        )
    if "prompt_optimizer_version" not in columns:
        op.add_column(
            "image_jobs",
            sa.Column("prompt_optimizer_version", sa.String(length=32), nullable=True),
        )
    if "reference_image_used" not in columns:
        op.add_column(
            "image_jobs",
            sa.Column(
                "reference_image_used",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    columns = _columns("image_jobs")
    if "reference_image_used" in columns:
        op.drop_column("image_jobs", "reference_image_used")
    if "prompt_optimizer_version" in columns:
        op.drop_column("image_jobs", "prompt_optimizer_version")
    if "source_prompt" in columns:
        op.drop_column("image_jobs", "source_prompt")
    op.alter_column(
        "ai_calls",
        "purpose",
        existing_type=sa.String(length=64),
        type_=sa.String(length=24),
        existing_nullable=False,
    )
