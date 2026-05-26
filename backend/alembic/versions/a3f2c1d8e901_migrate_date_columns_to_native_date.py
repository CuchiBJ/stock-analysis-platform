"""migrate_date_columns_to_native_date

Revision ID: a3f2c1d8e901
Revises: bd0a90e13734
Create Date: 2026-05-24

Migrates stock_prices.date and stock_metrics.date from VARCHAR(10) to DATE.
All existing values are YYYY-MM-DD and cast cleanly — verified before migration.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a3f2c1d8e901'
down_revision = 'bd0a90e13734'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'stock_prices', 'date',
        type_=sa.Date(),
        postgresql_using='date::date',
        existing_type=sa.String(10),
        existing_nullable=False,
    )
    op.alter_column(
        'stock_metrics', 'date',
        type_=sa.Date(),
        postgresql_using='date::date',
        existing_type=sa.String(10),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'stock_prices', 'date',
        type_=sa.String(10),
        postgresql_using='date::text',
        existing_type=sa.Date(),
        existing_nullable=False,
    )
    op.alter_column(
        'stock_metrics', 'date',
        type_=sa.String(10),
        postgresql_using='date::text',
        existing_type=sa.Date(),
        existing_nullable=False,
    )
