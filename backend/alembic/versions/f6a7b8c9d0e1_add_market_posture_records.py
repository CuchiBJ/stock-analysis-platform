"""add_market_posture_records

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_posture_records",
        sa.Column("session_date", sa.Date(), primary_key=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "state IN ('FUERA', 'DEFENSIVO', 'SELECTIVO', 'NORMAL', 'AGRESIVO')",
            name="ck_market_posture_records_known_state",
        ),
    )


def downgrade() -> None:
    op.drop_table("market_posture_records")
