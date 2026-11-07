"""Add PolyU email login fields.

Revision ID: 0002_email_login
Revises: 0001_initial
Create Date: 2026-11-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0002_email_login"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _unique_names(inspector) -> set:
    names = {item.get("name") for item in inspector.get_unique_constraints("participants")}
    names.update(
        item.get("name")
        for item in inspector.get_indexes("participants")
        if item.get("unique")
    )
    return {name for name in names if name}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("participants")}

    if "email" not in columns:
        op.add_column(
            "participants", sa.Column("email", sa.String(length=320), nullable=True)
        )
    if not columns.get("access_code_hmac", {}).get("nullable", True):
        op.alter_column("participants", "access_code_hmac", nullable=True)
    if not columns.get("access_code_last4", {}).get("nullable", True):
        op.alter_column("participants", "access_code_last4", nullable=True)

    inspector = inspect(bind)
    if "uq_participant_email" not in _unique_names(inspector):
        op.create_unique_constraint(
            "uq_participant_email", "participants", ["email"]
        )
    index_names = {item.get("name") for item in inspector.get_indexes("participants")}
    if "ix_participants_email" not in index_names:
        op.create_index("ix_participants_email", "participants", ["email"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    index_names = {item.get("name") for item in inspector.get_indexes("participants")}
    if "ix_participants_email" in index_names:
        op.drop_index("ix_participants_email", table_name="participants")
    if "uq_participant_email" in _unique_names(inspector):
        op.drop_constraint("uq_participant_email", "participants", type_="unique")
    columns = {column["name"] for column in inspector.get_columns("participants")}
    if "email" in columns:
        op.drop_column("participants", "email")
