"""add_journal_stop_history

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f5a6b7c8d9e0'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'journal_trades',
        sa.Column('initial_stop_price', sa.Float(), nullable=True),
    )
    op.create_table(
        'journal_stop_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('trade_id', sa.Integer(), nullable=False),
        sa.Column('old_stop_price', sa.Float(), nullable=True),
        sa.Column('new_stop_price', sa.Float(), nullable=True),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('auto_classified', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_journal_stop_events_trade', 'journal_stop_events', ['trade_id', 'occurred_at'])


def downgrade() -> None:
    op.drop_index('ix_journal_stop_events_trade', table_name='journal_stop_events')
    op.drop_table('journal_stop_events')
    op.drop_column('journal_trades', 'initial_stop_price')
