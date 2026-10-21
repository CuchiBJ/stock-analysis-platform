"""Reset legacy entering-pullback outcomes for chronological recomputation.

Revision ID: e5f6a7b8c9d0
Revises: d9e0f1a2b3c4

No detection context or stored OHLC is changed. Downgrade cannot restore old
labels; it resets results again for evaluation by the prior implementation.
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def _reset_terminal_pullbacks() -> None:
    op.execute(sa.text("""
        UPDATE transition_observations
        SET outcome_status = 'PENDING',
            outcome_evaluated_at = NULL,
            price_1d = NULL, price_5d = NULL, price_20d = NULL,
            pct_1d = NULL, pct_5d = NULL, pct_20d = NULL,
            max_gain_within_10d = NULL, max_drawdown_within_10d = NULL,
            max_gain_atr_within_10d = NULL, max_drawdown_atr_within_10d = NULL,
            reached_ema21_within_10d = NULL, broke_ema50_within_10d = NULL
        WHERE transition_type = 'entering_pullback'
          AND outcome_status IN ('SUCCESS', 'FAILURE', 'NEUTRAL', 'INSUFFICIENT_DATA')
    """))


def upgrade() -> None:
    _reset_terminal_pullbacks()


def downgrade() -> None:
    _reset_terminal_pullbacks()
