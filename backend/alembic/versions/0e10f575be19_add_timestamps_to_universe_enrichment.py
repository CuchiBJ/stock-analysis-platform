"""add_timestamps_to_universe_enrichment

Revision ID: 0e10f575be19
Revises: add_universe_engine
Create Date: 2026-05-19 14:21:07.596925

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e10f575be19'
down_revision = 'add_universe_engine'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add created_at and updated_at columns to universe_enrichment table
    op.add_column('universe_enrichment', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('universe_enrichment', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    
    # Add created_at and updated_at columns to universe_tiers table
    op.add_column('universe_tiers', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('universe_tiers', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))


def downgrade() -> None:
    # Remove created_at and updated_at columns from universe_tiers table
    op.drop_column('universe_tiers', 'updated_at')
    op.drop_column('universe_tiers', 'created_at')
    
    # Remove created_at and updated_at columns from universe_enrichment table
    op.drop_column('universe_enrichment', 'updated_at')
    op.drop_column('universe_enrichment', 'created_at')
