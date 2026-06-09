"""add_journal_trades

Revision ID: b1c2d3e4f5a6
Revises: a7e1b9c2d4f0
Create Date: 2026-06-02 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = 'a7e1b9c2d4f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'journal_trades',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('setup', sa.String(32), nullable=False, server_default='unknown'),
        sa.Column('context', sa.String(32), nullable=False, server_default='unknown'),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('stop_price', sa.Float(), nullable=True),
        sa.Column('cost_total', sa.Float(), nullable=True),
        sa.Column('exit_date', sa.Date(), nullable=True),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('duration_days', sa.Float(), nullable=True),
        sa.Column('pnl_dollars', sa.Float(), nullable=True),
        sa.Column('pnl_pct', sa.Float(), nullable=True),
        sa.Column('r_multiple', sa.Float(), nullable=True),
        sa.Column('error_note', sa.Text(), nullable=True),
        sa.Column('post_venta', sa.Text(), nullable=True),
        sa.Column('linked_observation_id', sa.Integer(), nullable=True),
        sa.Column('source_row', sa.Integer(), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_journal_symbol_entry', 'journal_trades', ['symbol', 'entry_date'])
    op.create_index('ix_journal_setup_context', 'journal_trades', ['setup', 'context'])


def downgrade() -> None:
    op.drop_index('ix_journal_setup_context', table_name='journal_trades')
    op.drop_index('ix_journal_symbol_entry', table_name='journal_trades')
    op.drop_table('journal_trades')
