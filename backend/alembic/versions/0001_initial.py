"""Initial Heritage Learning Studio schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The first revision materializes the reviewed SQLAlchemy metadata. Later
    # revisions must use explicit operations so schema evolution stays audited.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
