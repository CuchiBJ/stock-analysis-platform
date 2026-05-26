"""add_scheduler_errors

Revision ID: 930904ebf606
Revises: 4756279bdea1
Create Date: 2026-05-26 14:08:13.578995

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '930904ebf606'
down_revision = '4756279bdea1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scheduler_errors',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_name', sa.String(100), nullable=False),
        sa.Column('exception_type', sa.String(100), nullable=False),
        sa.Column('exception_message', sa.Text(), nullable=False),
        sa.Column('traceback', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_scheduler_errors_occurred_at', 'scheduler_errors', ['occurred_at'])
    op.create_index('ix_scheduler_errors_task_name', 'scheduler_errors', ['task_name'])


def downgrade() -> None:
    op.drop_index('ix_scheduler_errors_task_name', table_name='scheduler_errors')
    op.drop_index('ix_scheduler_errors_occurred_at', table_name='scheduler_errors')
    op.drop_table('scheduler_errors')
