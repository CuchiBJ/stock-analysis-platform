"""add identity tables

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-09-22 00:00:00.000000

"""

from alembic import context, op
import sqlalchemy as sa


revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        sa.CheckConstraint(
            "state IN ('pending_verification', 'active', 'disabled')",
            name="ck_users_state",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_state", "users", ["state"], unique=False)

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "length(trim(display_name)) BETWEEN 1 AND 80",
            name="ck_user_profiles_display_name_length",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_profiles_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_profiles"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "length(token_digest) = 64", name="ck_auth_sessions_token_digest_length"
        ),
        sa.CheckConstraint(
            "length(csrf_token_digest) = 64", name="ck_auth_sessions_csrf_digest_length"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_digest", name="uq_auth_sessions_token_digest"),
    )
    op.create_index(
        "ix_auth_sessions_user_expires",
        "auth_sessions",
        ["user_id", "expires_at"],
        unique=False,
    )

    _create_single_use_token_table(
        "email_verification_tokens",
        "ck_email_verification_tokens_digest_length",
        "fk_email_verification_tokens_user_id_users",
        "pk_email_verification_tokens",
        "uq_email_verification_tokens_token_digest",
        "ix_email_verification_tokens_user_expires",
    )
    _create_single_use_token_table(
        "password_reset_tokens",
        "ck_password_reset_tokens_digest_length",
        "fk_password_reset_tokens_user_id_users",
        "pk_password_reset_tokens",
        "uq_password_reset_tokens_token_digest",
        "ix_password_reset_tokens_user_expires",
    )

    # Expand journal ownership without guessing which user owns legacy data.
    # The claim command fills this column before the contract migration.
    op.add_column(
        "journal_trades",
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_journal_owner_entry",
        "journal_trades",
        ["owner_user_id", "entry_date"],
        unique=False,
    )
    op.create_index(
        "ix_journal_owner_symbol_entry",
        "journal_trades",
        ["owner_user_id", "symbol", "entry_date"],
        unique=False,
    )
    op.create_index(
        "ix_journal_owner_exit_date",
        "journal_trades",
        ["owner_user_id", "exit_date"],
        unique=False,
    )
    op.create_index(
        "ix_journal_owner_parent_trade",
        "journal_trades",
        ["owner_user_id", "parent_trade_id"],
        unique=False,
    )

    # Broker identifiers are private to an account, not globally unique.
    op.drop_index("ix_journal_broker_exec_id", table_name="journal_trades")
    op.create_index(
        "uq_journal_owner_broker_exec",
        "journal_trades",
        ["owner_user_id", "broker_exec_id"],
        unique=True,
    )

    _abort_if_rows_exist(
        """
        SELECT 1
        FROM journal_stop_events event
        LEFT JOIN journal_trades trade ON trade.id = event.trade_id
        WHERE trade.id IS NULL
        """,
        "journal_stop_events contains orphan trade_id values",
    )
    op.create_foreign_key(
        "fk_journal_stop_events_trade_id_journal_trades",
        "journal_stop_events",
        "journal_trades",
        ["trade_id"],
        ["id"],
        ondelete="CASCADE",
    )


def _create_single_use_token_table(
    table_name: str,
    digest_constraint: str,
    foreign_key_constraint: str,
    primary_key_constraint: str,
    unique_constraint: str,
    expiry_index: str,
) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(token_digest) = 64", name=digest_constraint),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=foreign_key_constraint, ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=primary_key_constraint),
        sa.UniqueConstraint("token_digest", name=unique_constraint),
    )
    op.create_index(expiry_index, table_name, ["user_id", "expires_at"], unique=False)


def _abort_if_rows_exist(query: str, message: str) -> None:
    """Validate legacy data online and emit an equivalent PostgreSQL guard offline."""
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


def downgrade() -> None:
    op.drop_constraint(
        "fk_journal_stop_events_trade_id_journal_trades",
        "journal_stop_events",
        type_="foreignkey",
    )
    op.drop_index("uq_journal_owner_broker_exec", table_name="journal_trades")
    op.create_index(
        "ix_journal_broker_exec_id",
        "journal_trades",
        ["broker_exec_id"],
        unique=True,
    )
    op.drop_index("ix_journal_owner_parent_trade", table_name="journal_trades")
    op.drop_index("ix_journal_owner_exit_date", table_name="journal_trades")
    op.drop_index("ix_journal_owner_symbol_entry", table_name="journal_trades")
    op.drop_index("ix_journal_owner_entry", table_name="journal_trades")
    op.drop_column("journal_trades", "owner_user_id")

    op.drop_index(
        "ix_password_reset_tokens_user_expires", table_name="password_reset_tokens"
    )
    op.drop_table("password_reset_tokens")
    op.drop_index(
        "ix_email_verification_tokens_user_expires",
        table_name="email_verification_tokens",
    )
    op.drop_table("email_verification_tokens")
    op.drop_index("ix_auth_sessions_user_expires", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("user_profiles")
    op.drop_index("ix_users_state", table_name="users")
    op.drop_table("users")
