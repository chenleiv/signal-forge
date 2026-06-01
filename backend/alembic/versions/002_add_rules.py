"""add rules table

Revision ID: 002
Revises: 001
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rules',
        sa.Column('id',          sa.String(8),              nullable=False),
        sa.Column('name',        sa.Text(),                 nullable=False),
        sa.Column('enabled',     sa.Boolean(),              nullable=False, server_default='true'),
        sa.Column('conditions',  sa.Text(),                 nullable=False, server_default='[]'),
        sa.Column('logic',       sa.String(3),              nullable=False, server_default='AND'),
        sa.Column('actions',     sa.Text(),                 nullable=False, server_default='[]'),
        sa.Column('match_count', sa.Integer(),              nullable=False, server_default='0'),
        sa.Column('created_at',  sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('rules')
