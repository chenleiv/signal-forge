"""users: session_key (per-account session revocation) and deleted_at (soft delete)

Revision ID: 005
Revises: 004
Create Date: 2026-09-26
"""
import secrets

from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('session_key', sa.String(64), nullable=True))
        batch.add_column(sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True))
    # Give every existing account its own key. Existing session tokens have no
    # key, so everyone logs in once after this migration.
    conn = op.get_bind()
    for (username,) in conn.execute(sa.text("SELECT username FROM users")).fetchall():
        conn.execute(sa.text("UPDATE users SET session_key = :k WHERE username = :u"),
                     {"k": secrets.token_hex(16), "u": username})


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('deleted_at')
        batch.drop_column('session_key')
