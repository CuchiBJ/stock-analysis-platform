"""add_journal_broker_sync

Adds broker auto-sync provenance columns to journal_trades so IBKR Flex
executions can be imported idempotently (dedupe by broker_exec_id) while
preserving manual annotations across the open→closed transition.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-06-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c8d9e0f1a2'
down_revision = 'a6b7c8d9e0f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'journal_trades',
        sa.Column('broker_exec_id', sa.String(64), nullable=True),
    )
    op.add_column(
        'journal_trades',
        sa.Column('broker_open_exec_id', sa.String(64), nullable=True),
    )
    # Unique so a re-sync can't insert the same execution twice. NULLs (manual /
    # CSV trades) are exempt from the uniqueness check in Postgres.
    op.create_index(
        'ix_journal_broker_exec_id',
        'journal_trades',
        ['broker_exec_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_journal_broker_exec_id', table_name='journal_trades')
    op.drop_column('journal_trades', 'broker_open_exec_id')
    op.drop_column('journal_trades', 'broker_exec_id')
