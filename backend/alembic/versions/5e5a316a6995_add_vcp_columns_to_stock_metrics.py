"""add_vcp_columns_to_stock_metrics

Revision ID: 5e5a316a6995
Revises: 315fbb7a8d64
Create Date: 2026-05-23 12:36:31.898248

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e5a316a6995'
down_revision = '315fbb7a8d64'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('stock_metrics', sa.Column('vcp_contractions_count', sa.Integer(), nullable=True))
    op.add_column('stock_metrics', sa.Column('vcp_latest_depth_pct', sa.Float(), nullable=True))
    op.add_column('stock_metrics', sa.Column('vcp_score', sa.Float(), nullable=True))
    op.create_index('ix_stock_metrics_vcp_score', 'stock_metrics', ['vcp_score'])


def downgrade() -> None:
    op.drop_index('ix_stock_metrics_vcp_score', 'stock_metrics')
    op.drop_column('stock_metrics', 'vcp_score')
    op.drop_column('stock_metrics', 'vcp_latest_depth_pct')
    op.drop_column('stock_metrics', 'vcp_contractions_count')
