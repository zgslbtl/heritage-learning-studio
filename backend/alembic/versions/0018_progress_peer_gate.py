"""Add progress gates and reversible participant stops without altering history."""
from alembic import op
import sqlalchemy as sa

revision = "0018_progress_peer_gate"
down_revision = "0017_recoverable_class_links"
branch_labels = None
depends_on = None


def upgrade():
    additions = {
        "runs": [sa.Column("last_operation_at", sa.DateTime(timezone=True)),
                 sa.Column("stopped_at", sa.DateTime(timezone=True)),
                 sa.Column("stop_reason", sa.Text())],
        "class_peer_gates": [sa.Column("policy_version", sa.String(48)),
                             sa.Column("timer_started_at", sa.DateTime(timezone=True)),
                             sa.Column("opening_reason", sa.String(32)),
                             sa.Column("snapshot_json", sa.JSON(), nullable=False, server_default="{}")],
        "peer_assignments": [sa.Column("allocation_kind", sa.String(16), nullable=False, server_default="main")],
    }
    for table, columns in additions.items():
        existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)


def downgrade():
    # Operational rollback keeps this additive schema and all new audit data.
    for table, columns in {"peer_assignments": ["allocation_kind"],
                           "class_peer_gates": ["snapshot_json", "opening_reason", "timer_started_at", "policy_version"],
                           "runs": ["stop_reason", "stopped_at", "last_operation_at"]}.items():
        for name in columns:
            op.drop_column(table, name)
