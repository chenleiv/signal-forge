"""add users table; clear display-name assignments

Revision ID: 004
Revises: 003
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('username',      sa.String(50),               nullable=False, primary_key=True),
        sa.Column('display_name',  sa.String(100),              nullable=False),
        sa.Column('password_hash', sa.String(100),              nullable=False),
        sa.Column('role',          sa.String(10),               nullable=False),
        sa.Column('created_at',    sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'analyst')", name='ck_users_role'),
    )
    # assigned_to used to hold display names ("Alice Chen"); it now holds
    # usernames. None of the old values is a valid username, so clear them.
    op.execute("UPDATE incidents SET assigned_to = NULL")


def downgrade() -> None:
    op.drop_table('users')
