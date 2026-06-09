"""add_journal_risk_tracking

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd3e4f5a6b7c8'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'journal_trades',
        sa.Column('planned_risk_dollars', sa.Float(), nullable=True),
    )
    op.add_column(
        'journal_trades',
        sa.Column('account_balance_at_entry', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('journal_trades', 'account_balance_at_entry')
    op.drop_column('journal_trades', 'planned_risk_dollars')
