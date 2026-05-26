"""create_transition_observations

Revision ID: bd0a90e13734
Revises: 5e5a316a6995
Create Date: 2026-05-23 14:02:01.386865

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bd0a90e13734'
down_revision = '5e5a316a6995'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'transition_observations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('transition_type', sa.String(40), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('date_detected', sa.Date(), nullable=False),
        # context snapshot
        sa.Column('regime_at_detection', sa.String(20), nullable=True),
        sa.Column('price_at_detection', sa.Float(), nullable=True),
        sa.Column('ema9_at_detection', sa.Float(), nullable=True),
        sa.Column('ema21_at_detection', sa.Float(), nullable=True),
        sa.Column('ema50_at_detection', sa.Float(), nullable=True),
        sa.Column('atr_at_detection', sa.Float(), nullable=True),
        sa.Column('rs_spy_at_detection', sa.Float(), nullable=True),
        sa.Column('adr_percent_at_detection', sa.Float(), nullable=True),
        sa.Column('vcp_score_at_detection', sa.Float(), nullable=True),
        sa.Column('relative_volume_at_detection', sa.Float(), nullable=True),
        sa.Column('weekly_tightness_at_detection', sa.Float(), nullable=True),
        # outcome fields
        sa.Column('price_1d', sa.Float(), nullable=True),
        sa.Column('price_5d', sa.Float(), nullable=True),
        sa.Column('price_20d', sa.Float(), nullable=True),
        sa.Column('pct_1d', sa.Float(), nullable=True),
        sa.Column('pct_5d', sa.Float(), nullable=True),
        sa.Column('pct_20d', sa.Float(), nullable=True),
        sa.Column('max_gain_within_10d', sa.Float(), nullable=True),
        sa.Column('max_drawdown_within_10d', sa.Float(), nullable=True),
        sa.Column('max_gain_atr_within_10d', sa.Float(), nullable=True),
        sa.Column('max_drawdown_atr_within_10d', sa.Float(), nullable=True),
        sa.Column('reached_ema21_within_10d', sa.Boolean(), nullable=True),
        sa.Column('broke_ema50_within_10d', sa.Boolean(), nullable=True),
        sa.Column('outcome_status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('outcome_evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index(
        'ix_obs_symbol_type_date', 'transition_observations',
        ['symbol', 'transition_type', 'date_detected'], unique=True
    )
    op.create_index(
        'ix_obs_pending', 'transition_observations',
        ['outcome_status', 'date_detected'],
        postgresql_where=sa.text("outcome_status = 'PENDING'")
    )
    op.create_index(
        'ix_obs_aggregation', 'transition_observations',
        ['transition_type', 'regime_at_detection', 'outcome_status']
    )


def downgrade() -> None:
    op.drop_index('ix_obs_aggregation', 'transition_observations')
    op.drop_index('ix_obs_pending', 'transition_observations')
    op.drop_index('ix_obs_symbol_type_date', 'transition_observations')
    op.drop_table('transition_observations')
