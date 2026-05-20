"""merge_heads

Revision ID: 26659031c097
Revises: 617dcf928644, add_high_52w
Create Date: 2026-05-20 14:42:58.075009

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26659031c097'
down_revision = ('617dcf928644', 'add_high_52w')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
