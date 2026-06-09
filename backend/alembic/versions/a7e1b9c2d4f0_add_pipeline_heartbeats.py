"""add_pipeline_heartbeats

Revision ID: a7e1b9c2d4f0
Revises: 930904ebf606
Create Date: 2026-06-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7e1b9c2d4f0'
down_revision = '930904ebf606'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pipeline_heartbeats',
        sa.Column('cycle_name', sa.String(50), primary_key=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_duration_seconds', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('symbols_processed', sa.Integer(), nullable=True),
        sa.Column('symbols_expected', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'ok'")),
        sa.Column('last_error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('pipeline_heartbeats')
