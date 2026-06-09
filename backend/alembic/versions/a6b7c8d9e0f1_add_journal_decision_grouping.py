"""add_journal_decision_grouping

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-06-03 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a6b7c8d9e0f1'
down_revision = 'f5a6b7c8d9e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'journal_trades',
        sa.Column('parent_trade_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        'ix_journal_parent_trade_id', 'journal_trades', ['parent_trade_id']
    )


def downgrade() -> None:
    op.drop_index('ix_journal_parent_trade_id', table_name='journal_trades')
    op.drop_column('journal_trades', 'parent_trade_id')
