"""v1.5 product design, peer assessment and simulated social feed.

Revision ID: 0003_v15_products_peer_social
Revises: 0002_email_login
Create Date: 2026-11-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0003_v15_products_peer_social"
down_revision: Union[str, None] = "0002_email_login"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(inspector, table: str) -> set:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    run_columns = _column_names(inspector, "runs")
    if "t1_condition" not in run_columns:
        op.add_column(
            "runs", sa.Column("t1_condition", sa.String(length=1), nullable=True)
        )
    if "artifact_order" not in run_columns:
        op.add_column(
            "runs", sa.Column("artifact_order", sa.String(length=2), nullable=True)
        )

    round_columns = _column_names(inspector, "rounds")
    if "current_work_revision" not in round_columns:
        op.add_column(
            "rounds",
            sa.Column(
                "current_work_revision",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    image_columns = _column_names(inspector, "image_jobs")
    if "work_revision_no" not in image_columns:
        op.add_column(
            "image_jobs", sa.Column("work_revision_no", sa.Integer(), nullable=True)
        )

    existing_tables = set(inspector.get_table_names())
    if "work_revisions" not in existing_tables:
        op.create_table(
            "work_revisions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("round_id", sa.Uuid(), nullable=False),
            sa.Column("revision_no", sa.Integer(), nullable=False),
            sa.Column("product_name", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("product_category", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("target_audience", sa.String(length=300), nullable=False, server_default=""),
            sa.Column("design_concept", sa.Text(), nullable=False, server_default=""),
            sa.Column("structured_fields", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("open_statement", sa.Text(), nullable=False, server_default=""),
            sa.Column("source", sa.String(length=24), nullable=False, server_default="autosave"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["round_id"], ["rounds.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("round_id", "revision_no", name="uq_work_revision"),
        )
        op.create_index("ix_work_revisions_round_id", "work_revisions", ["round_id"])

    if "peer_batches" not in existing_tables:
        op.create_table(
            "peer_batches",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("class_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="frozen"),
            sa.Column("algorithm_version", sa.String(length=32), nullable=False, server_default="peer-v1"),
            sa.Column("scale_version", sa.String(length=32), nullable=False, server_default="peer-scale-v1"),
            sa.Column("eligible_work_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_peer_batches_class_id", "peer_batches", ["class_id"])

    if "peer_assignments" not in existing_tables:
        op.create_table(
            "peer_assignments",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("batch_id", sa.Uuid(), nullable=False),
            sa.Column("reviewer_run_id", sa.Uuid(), nullable=False),
            sa.Column("work_id", sa.BigInteger(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["peer_batches.id"]),
            sa.ForeignKeyConstraint(["reviewer_run_id"], ["runs.id"]),
            sa.ForeignKeyConstraint(["work_id"], ["work_revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("batch_id", "reviewer_run_id", "work_id", name="uq_peer_assignment"),
        )
        op.create_index("ix_peer_assignments_batch_id", "peer_assignments", ["batch_id"])
        op.create_index("ix_peer_assignments_reviewer_run_id", "peer_assignments", ["reviewer_run_id"])
        op.create_index("ix_peer_assignments_work_id", "peer_assignments", ["work_id"])

    if "peer_ratings" not in existing_tables:
        op.create_table(
            "peer_ratings",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("assignment_id", sa.Uuid(), nullable=False),
            sa.Column("scores_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("comment", sa.Text(), nullable=False, server_default=""),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["assignment_id"], ["peer_assignments.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("assignment_id"),
        )
        op.create_index("ix_peer_ratings_assignment_id", "peer_ratings", ["assignment_id"])

    if "social_views" not in existing_tables:
        op.create_table(
            "social_views",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("work_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
            sa.ForeignKeyConstraint(["work_id"], ["work_revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_social_views_run_id", "social_views", ["run_id"])
        op.create_index("ix_social_views_work_id", "social_views", ["work_id"])

    if "social_likes" not in existing_tables:
        op.create_table(
            "social_likes",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("work_id", sa.BigInteger(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
            sa.ForeignKeyConstraint(["work_id"], ["work_revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id", "work_id", name="uq_social_like"),
        )
        op.create_index("ix_social_likes_run_id", "social_likes", ["run_id"])
        op.create_index("ix_social_likes_work_id", "social_likes", ["work_id"])

    if "social_comments" not in existing_tables:
        op.create_table(
            "social_comments",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("work_id", sa.BigInteger(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
            sa.ForeignKeyConstraint(["work_id"], ["work_revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_social_comments_run_id", "social_comments", ["run_id"])
        op.create_index("ix_social_comments_work_id", "social_comments", ["work_id"])

    if "social_events" not in existing_tables:
        op.create_table(
            "social_events",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("work_id", sa.BigInteger(), nullable=False),
            sa.Column("event_type", sa.String(length=24), nullable=False),
            sa.Column("meta_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
            sa.ForeignKeyConstraint(["work_id"], ["work_revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_social_events_run_id", "social_events", ["run_id"])
        op.create_index("ix_social_events_work_id", "social_events", ["work_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table in (
        "social_events",
        "social_comments",
        "social_likes",
        "social_views",
        "peer_ratings",
        "peer_assignments",
        "peer_batches",
        "work_revisions",
    ):
        if table in inspector.get_table_names():
            op.drop_table(table)
    if "work_revision_no" in _column_names(inspector, "image_jobs"):
        op.drop_column("image_jobs", "work_revision_no")
    if "current_work_revision" in _column_names(inspector, "rounds"):
        op.drop_column("rounds", "current_work_revision")
    if "artifact_order" in _column_names(inspector, "runs"):
        op.drop_column("runs", "artifact_order")
    if "t1_condition" in _column_names(inspector, "runs"):
        op.drop_column("runs", "t1_condition")
