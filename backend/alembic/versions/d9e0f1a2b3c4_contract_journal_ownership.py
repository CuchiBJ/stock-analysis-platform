"""contract journal ownership

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-09-23 00:00:00.000000

This revision must run only after the administrator bootstrap, legacy claim,
and integrity validators have completed successfully.
"""

from alembic import context, op
import sqlalchemy as sa


revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _abort_if_rows_exist(
        "SELECT 1 FROM journal_trades WHERE owner_user_id IS NULL",
        "journal ownership contract refused: unclaimed trades remain",
    )
    _abort_if_rows_exist(
        """
        SELECT 1
        FROM journal_trades trade
        LEFT JOIN users owner ON owner.id = trade.owner_user_id
        WHERE owner.id IS NULL
        """,
        "journal ownership contract refused: unknown owners exist",
    )

    op.alter_column(
        "journal_trades",
        "owner_user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_journal_trades_owner_user_id_users",
        "journal_trades",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Schema-only downgrade: preserve all owner UUIDs while reopening the
    # nullable column for an auth-aware rollback release.
    op.drop_constraint(
        "fk_journal_trades_owner_user_id_users",
        "journal_trades",
        type_="foreignkey",
    )
    op.alter_column(
        "journal_trades",
        "owner_user_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def _abort_if_rows_exist(query: str, message: str) -> None:
    """Validate data online and keep PostgreSQL ``--sql`` output guarded."""
    if context.is_offline_mode():
        escaped_message = message.replace("'", "''")
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS ({query}) THEN
                    RAISE EXCEPTION '{escaped_message}';
                END IF;
            END;
            $$
            """
        )
        return

    if op.get_bind().execute(sa.text(f"SELECT EXISTS ({query})")).scalar():
        raise RuntimeError(message)
