"""revoked_sessions: logged-out session ids until their tokens expire

Revision ID: 007
Revises: 006
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'revoked_sessions',
        sa.Column('sid',        sa.String(32),               nullable=False, primary_key=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('revoked_sessions')
