"""threat_feed_snapshot: the last AbuseIPDB blacklist, kept across restarts

Revision ID: 008
Revises: 007
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'threat_feed_snapshot',
        sa.Column('id',       sa.Integer(),                nullable=False, primary_key=True),
        sa.Column('ips',      sa.Text(),                   nullable=False),
        sa.Column('saved_at', sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('threat_feed_snapshot')
