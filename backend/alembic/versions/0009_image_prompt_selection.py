"""Image prompt and selected concept image.

Revision ID: 0009_image_prompt_selection
Revises: 0008_work_submit_consent
Create Date: 2026-11-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0009_image_prompt_selection"
down_revision: Union[str, None] = "0008_work_submit_consent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "image_prompt" not in _columns("work_revisions"):
        op.add_column(
            "work_revisions",
            sa.Column("image_prompt", sa.Text(), nullable=False, server_default=""),
        )
    if "selected_image_job_id" not in _columns("rounds"):
        op.add_column(
            "rounds",
            sa.Column("selected_image_job_id", sa.Uuid(), nullable=True),
        )
        op.create_index(
            "ix_rounds_selected_image_job_id", "rounds", ["selected_image_job_id"]
        )


def downgrade() -> None:
    if "selected_image_job_id" in _columns("rounds"):
        op.drop_column("rounds", "selected_image_job_id")
    if "image_prompt" in _columns("work_revisions"):
        op.drop_column("work_revisions", "image_prompt")
