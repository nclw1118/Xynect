"""add door_items table

Revision ID: b1d0c4a2e5f1
Revises: ab362575a86c
Create Date: 2026-06-14 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1d0c4a2e5f1'
down_revision: Union[str, Sequence[str], None] = 'ab362575a86c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'door_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('tag', sa.String(length=64), nullable=True),
        sa.Column('material_type', sa.String(length=64), nullable=False),
        sa.Column('width', sa.String(length=64), nullable=True),
        sa.Column('height', sa.String(length=64), nullable=True),
        sa.Column('area', sa.String(length=64), nullable=True),
        sa.Column('quantity', sa.String(length=32), nullable=True),
        sa.Column('opening_type', sa.String(length=128), nullable=True),
        sa.Column('material', sa.String(length=128), nullable=True),
        sa.Column('fire_rating', sa.String(length=64), nullable=True),
        sa.Column('self_closing', sa.String(length=32), nullable=True),
        sa.Column('glass_type', sa.String(length=128), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('original_extraction', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('user_edits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('door_items')
