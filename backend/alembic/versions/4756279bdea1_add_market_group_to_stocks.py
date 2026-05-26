"""add_market_group_to_stocks

Revision ID: 4756279bdea1
Revises: a3f2c1d8e901
Create Date: 2026-05-25 22:51:44.633081

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4756279bdea1'
down_revision = 'a3f2c1d8e901'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('stocks', sa.Column('market_group', sa.String(50), nullable=True))
    op.create_index('ix_stocks_market_group', 'stocks', ['market_group'])


def downgrade() -> None:
    op.drop_index('ix_stocks_market_group', table_name='stocks')
    op.drop_column('stocks', 'market_group')
