"""Work-submission consent for future research use.

Revision ID: 0008_work_submit_consent
Revises: 0007_peer_impressions_config
Create Date: 2026-11-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0008_work_submit_consent"
down_revision: Union[str, None] = "0007_peer_impressions_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    columns = _columns("runs")
    if "consent_future_research" not in columns:
        op.add_column("runs", sa.Column("consent_future_research", sa.Boolean(), nullable=True))
    if "consent_recorded_at" not in columns:
        op.add_column("runs", sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True))
    if "consent_version" not in columns:
        op.add_column("runs", sa.Column("consent_version", sa.String(length=32), nullable=True))


def downgrade() -> None:
    columns = _columns("runs")
    if "consent_version" in columns:
        op.drop_column("runs", "consent_version")
    if "consent_recorded_at" in columns:
        op.drop_column("runs", "consent_recorded_at")
    if "consent_future_research" in columns:
        op.drop_column("runs", "consent_future_research")
