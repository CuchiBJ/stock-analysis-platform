"""add_journal_system_snapshots

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-03 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('journal_trades', sa.Column('regime_at_entry', sa.String(40), nullable=True))
    op.add_column('journal_trades', sa.Column('system_score_at_entry', sa.Float(), nullable=True))
    op.add_column('journal_trades', sa.Column('group_strength_at_entry', sa.String(16), nullable=True))
    op.add_column('journal_trades', sa.Column('leader_health_at_entry', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('journal_trades', 'leader_health_at_entry')
    op.drop_column('journal_trades', 'group_strength_at_entry')
    op.drop_column('journal_trades', 'system_score_at_entry')
    op.drop_column('journal_trades', 'regime_at_entry')
