"""Allow Class 0 personal snapshots while retaining formal class uniqueness."""
from alembic import op
import sqlalchemy as sa

revision = "0015_beta_peer_snapshots"
down_revision = "0014_cloud_runtime"
branch_labels = None
depends_on = None


def upgrade():
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("peer_batches")}
    if "uq_peer_batch_active" in indexes:
        op.drop_index("uq_peer_batch_active", table_name="peer_batches")
    op.create_index("uq_peer_batch_active", "peer_batches", ["class_id"], unique=True,
                    postgresql_where=sa.text("status <> 'superseded' AND (class_id <> 0 OR algorithm_version <> 'beta-continuous-v1')"))
    if "uq_beta_peer_reviewer_snapshot" not in indexes:
        op.create_index("uq_beta_peer_reviewer_snapshot", "peer_batches",
                        [sa.text("(config_json ->> 'reviewer_run_id')")], unique=True,
                        postgresql_where=sa.text("class_id = 0 AND algorithm_version = 'beta-continuous-v1'"))


def downgrade():
    duplicates = op.get_bind().execute(sa.text(
        "SELECT class_id FROM peer_batches WHERE status <> 'superseded' GROUP BY class_id HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicates:
        raise RuntimeError("Keep beta snapshots: roll back application code without downgrading this index migration.")
    op.drop_index("uq_beta_peer_reviewer_snapshot", table_name="peer_batches")
    op.drop_index("uq_peer_batch_active", table_name="peer_batches")
    op.create_index("uq_peer_batch_active", "peer_batches", ["class_id"], unique=True,
                    postgresql_where=sa.text("status <> 'superseded'"))
