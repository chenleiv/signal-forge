"""add behavioral_settings table

Revision ID: 003
Revises: 002
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'behavioral_settings',
        sa.Column('id',                   sa.Integer(),              nullable=False, primary_key=True),
        sa.Column('repeated_threshold',   sa.Integer(),              nullable=False, server_default='8'),
        sa.Column('escalation_delta',     sa.Integer(),              nullable=False, server_default='20'),
        sa.Column('cooldown_min',         sa.Integer(),              nullable=False, server_default='30'),
        sa.Column('created_at',           sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at',           sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('behavioral_settings')
