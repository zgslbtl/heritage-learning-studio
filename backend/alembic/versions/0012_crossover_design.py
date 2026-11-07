"""Four-group balanced crossover design metadata.

Revision ID: 0012_crossover_design
Revises: 0011_image_prompt_optimizer
Create Date: 2026-11-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0012_crossover_design"
down_revision: Union[str, None] = "0011_image_prompt_optimizer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns("runs")}


def upgrade() -> None:
    columns = _columns()
    if "design_version" not in columns:
        op.add_column("runs", sa.Column("design_version", sa.String(length=32), nullable=True))
    if "condition_sequence" not in columns:
        op.add_column("runs", sa.Column("condition_sequence", sa.String(length=2), nullable=True))
    if "artifact_sequence" not in columns:
        op.add_column("runs", sa.Column("artifact_sequence", sa.String(length=2), nullable=True))


def downgrade() -> None:
    columns = _columns()
    if "artifact_sequence" in columns:
        op.drop_column("runs", "artifact_sequence")
    if "condition_sequence" in columns:
        op.drop_column("runs", "condition_sequence")
    if "design_version" in columns:
        op.drop_column("runs", "design_version")
