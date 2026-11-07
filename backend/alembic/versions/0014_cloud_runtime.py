"""Add isolated cloud outbox/checkpoints and shared login rate limits."""
from alembic import op
import sqlalchemy as sa

revision = "0014_cloud_runtime"
down_revision = "0013_assessment_v2"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "runtime_tasks" not in existing:
        op.create_table("runtime_tasks",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("dispatch_state", sa.String(16), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("checkpoint", sa.JSON(), nullable=False),
            sa.Column("error_code", sa.String(64)),
            sa.Column("file_key", sa.String(512)),
            sa.Column("lease_until", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_runtime_tasks_status", "runtime_tasks", ["status"])
        op.create_index("ix_runtime_tasks_dispatch_state", "runtime_tasks", ["dispatch_state"])
    if "rate_limit_buckets" not in existing:
        op.create_table("rate_limit_buckets",
            sa.Column("key", sa.String(64), primary_key=True),
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False))



def downgrade():
    op.drop_table("rate_limit_buckets")
    op.drop_table("runtime_tasks")
