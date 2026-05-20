"""add_atr_to_stock_metrics

Revision ID: 617dcf928644
Revises: 0e10f575be19
Create Date: 2026-05-20 13:39:38.198250

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '617dcf928644'
down_revision = '0e10f575be19'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('stock_metrics', sa.Column('atr', sa.Float(), nullable=True))
    op.add_column('stock_metrics', sa.Column('atr_percent', sa.Float(), nullable=True))
    op.add_column('stock_metrics', sa.Column('distance_to_ema9_atr', sa.Float(), nullable=True))
    op.add_column('stock_metrics', sa.Column('distance_to_ema21_atr', sa.Float(), nullable=True))
    op.add_column('stock_metrics', sa.Column('distance_to_ema50_atr', sa.Float(), nullable=True))
    op.add_column('stock_metrics', sa.Column('distance_to_high_52w_atr', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('stock_metrics', 'distance_to_high_52w_atr')
    op.drop_column('stock_metrics', 'distance_to_ema50_atr')
    op.drop_column('stock_metrics', 'distance_to_ema21_atr')
    op.drop_column('stock_metrics', 'distance_to_ema9_atr')
    op.drop_column('stock_metrics', 'atr_percent')
    op.drop_column('stock_metrics', 'atr')
