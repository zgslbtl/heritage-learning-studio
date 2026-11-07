"""Formal artifact sections/media, parallel assessment forms and research keys.

Revision ID: 0006_formal_content_forms_media
Revises: 0005_class_entry_links
Create Date: 2026-11-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0006_formal_content_forms_media"
down_revision: Union[str, None] = "0005_class_entry_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    # 0001_initial materializes the current metadata on a fresh database, so
    # every operation below is deliberately conditional.
    _add_column("artifact_versions", sa.Column("object_code", sa.String(length=1), nullable=True))
    _add_column("artifact_versions", sa.Column("sections_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    _add_column("artifact_versions", sa.Column("media_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    _add_column("artifact_versions", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    _add_column(
        "artifact_versions",
        sa.Column("rights_status", sa.String(length=32), nullable=False, server_default="internal-research"),
    )

    _add_column("instrument_versions", sa.Column("object_code", sa.String(length=1), nullable=True))
    _add_column("instrument_versions", sa.Column("form_code", sa.String(length=1), nullable=True))

    _add_column(
        "protocol_versions",
        sa.Column("research_rubric_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    _add_column("runs", sa.Column("object_order", sa.String(length=2), nullable=True))
    _add_column("runs", sa.Column("test_form_order", sa.String(length=2), nullable=True))

    _add_column(
        "evidence_events",
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    _add_column(
        "assessment_responses",
        sa.Column("score_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    _add_column("assessment_responses", sa.Column("score_total", sa.Integer(), nullable=True))
    _add_column("assessment_responses", sa.Column("scoring_version", sa.String(length=32), nullable=True))
    _add_column("assessment_responses", sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True))

    existing = _tables()
    if "protocol_assessment_forms" not in existing:
        op.create_table(
            "protocol_assessment_forms",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("protocol_version_id", sa.Uuid(), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("object_code", sa.String(length=1), nullable=False),
            sa.Column("form_code", sa.String(length=1), nullable=False),
            sa.Column("instrument_version_id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(["protocol_version_id"], ["protocol_versions.id"]),
            sa.ForeignKeyConstraint(["instrument_version_id"], ["instrument_versions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "protocol_version_id",
                "kind",
                "object_code",
                "form_code",
                name="uq_protocol_assessment_form",
            ),
        )
        op.create_index(
            "ix_protocol_assessment_forms_protocol_version_id",
            "protocol_assessment_forms",
            ["protocol_version_id"],
        )

    if "assessment_item_keys" not in existing:
        op.create_table(
            "assessment_item_keys",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("instrument_version_id", sa.Uuid(), nullable=False),
            sa.Column("question_id", sa.String(length=60), nullable=False),
            sa.Column("correct_value", sa.String(length=80), nullable=True),
            sa.Column("max_score", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("construct", sa.String(length=16), nullable=True),
            sa.Column("dimension", sa.String(length=32), nullable=True),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.ForeignKeyConstraint(["instrument_version_id"], ["instrument_versions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "instrument_version_id",
                "question_id",
                name="uq_assessment_item_key",
            ),
        )
        op.create_index(
            "ix_assessment_item_keys_instrument_version_id",
            "assessment_item_keys",
            ["instrument_version_id"],
        )

    indexes = {item.get("name") for item in inspect(op.get_bind()).get_indexes("artifact_versions")}
    if "ix_artifact_versions_object_code" not in indexes:
        op.create_index("ix_artifact_versions_object_code", "artifact_versions", ["object_code"])
    indexes = {item.get("name") for item in inspect(op.get_bind()).get_indexes("instrument_versions")}
    if "ix_instrument_versions_object_code" not in indexes:
        op.create_index("ix_instrument_versions_object_code", "instrument_versions", ["object_code"])
    if "ix_instrument_versions_form_code" not in indexes:
        op.create_index("ix_instrument_versions_form_code", "instrument_versions", ["form_code"])


def downgrade() -> None:
    existing = _tables()
    if "assessment_item_keys" in existing:
        op.drop_table("assessment_item_keys")
    if "protocol_assessment_forms" in existing:
        op.drop_table("protocol_assessment_forms")
    for table, column in (
        ("assessment_responses", "scored_at"),
        ("assessment_responses", "scoring_version"),
        ("assessment_responses", "score_total"),
        ("assessment_responses", "score_json"),
        ("evidence_events", "meta_json"),
        ("runs", "test_form_order"),
        ("runs", "object_order"),
        ("protocol_versions", "research_rubric_json"),
        ("instrument_versions", "form_code"),
        ("instrument_versions", "object_code"),
        ("artifact_versions", "rights_status"),
        ("artifact_versions", "content_sha256"),
        ("artifact_versions", "media_json"),
        ("artifact_versions", "sections_json"),
        ("artifact_versions", "object_code"),
    ):
        if column in _columns(table):
            op.drop_column(table, column)
