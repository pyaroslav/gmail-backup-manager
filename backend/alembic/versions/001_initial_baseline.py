"""Initial baseline - stamp existing schema.

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-08

This is a baseline migration. The schema already exists in the database,
so upgrade() and downgrade() are intentionally empty. Run
`alembic stamp 001_initial` to mark the database as being at this revision
without actually executing any SQL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline migration - schema already exists.
    pass


def downgrade() -> None:
    # Baseline migration - nothing to revert.
    pass
