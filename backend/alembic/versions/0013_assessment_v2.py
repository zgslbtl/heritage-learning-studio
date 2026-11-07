"""Assessment V2 pilot: rationale fields and version metadata.

Revision ID: 0013_assessment_v2
Revises: 0012_crossover_design
Create Date: 2026-11-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0013_assessment_v2"
down_revision: Union[str, None] = "0012_crossover_design"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    run_columns = _columns("runs")
    if "design_version" in run_columns:
        op.alter_column(
            "runs",
            "design_version",
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=True,
        )

    protocol_columns = _columns("protocol_versions")
    if "assessment_version" not in protocol_columns:
        op.add_column(
            "protocol_versions",
            sa.Column("assessment_version", sa.String(length=64), nullable=True),
        )

    work_columns = _columns("work_revisions")
    if "rationale_fields" not in work_columns:
        op.add_column(
            "work_revisions",
            sa.Column(
                "rationale_fields",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )


def downgrade() -> None:
    work_columns = _columns("work_revisions")
    if "rationale_fields" in work_columns:
        op.drop_column("work_revisions", "rationale_fields")

    protocol_columns = _columns("protocol_versions")
    if "assessment_version" in protocol_columns:
        op.drop_column("protocol_versions", "assessment_version")

    run_columns = _columns("runs")
    if "design_version" in run_columns:
        op.alter_column(
            "runs",
            "design_version",
            existing_type=sa.String(length=64),
            type_=sa.String(length=32),
            existing_nullable=True,
        )
