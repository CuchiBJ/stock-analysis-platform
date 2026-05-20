"""add high_52w to stock_metrics

Revision ID: add_high_52w
Revises: 
Create Date: 2026-05-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_high_52w'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('stock_metrics', sa.Column('high_52w', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('stock_metrics', 'high_52w')
