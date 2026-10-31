"""add NFRC fields (u_value/shgc/vt) to door_items

Glazed doors (sliding glass, glass entry) carry NFRC performance ratings in
energy/opening schedules. These columns were previously window-only.

Revision ID: c2e1f3a4b5d6
Revises: b1d0c4a2e5f1
Create Date: 2026-10-31 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c2e1f3a4b5d6'
down_revision: Union[str, Sequence[str], None] = 'b1d0c4a2e5f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('door_items', sa.Column('u_value', sa.String(length=32), nullable=True))
    op.add_column('door_items', sa.Column('shgc', sa.String(length=32), nullable=True))
    op.add_column('door_items', sa.Column('vt', sa.String(length=32), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('door_items', 'vt')
    op.drop_column('door_items', 'shgc')
    op.drop_column('door_items', 'u_value')
