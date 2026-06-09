"""add_journal_decision_provenance

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-03 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'journal_trades',
        sa.Column('from_queue', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'journal_trades',
        sa.Column('entry_reason', sa.String(20), nullable=False, server_default='other'),
    )
    op.add_column(
        'journal_trades',
        sa.Column('exit_reason', sa.String(20), nullable=False, server_default='unknown'),
    )


def downgrade() -> None:
    op.drop_column('journal_trades', 'exit_reason')
    op.drop_column('journal_trades', 'entry_reason')
    op.drop_column('journal_trades', 'from_queue')
