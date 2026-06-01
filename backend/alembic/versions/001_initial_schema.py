"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('attack_type', sa.String(50), nullable=False),
        sa.Column('source_ip', sa.String(45), nullable=True),
        sa.Column('source_region', sa.String(10), nullable=True),
        sa.Column('event_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mitre_tags', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('assigned_to', sa.String(100), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'notes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('incident_id', sa.String(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('author', sa.String(100), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'incident_tasks',
        sa.Column('incident_id', sa.String(), nullable=False),
        sa.Column('task_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('incident_id', 'task_index'),
    )


def downgrade() -> None:
    op.drop_table('incident_tasks')
    op.drop_table('notes')
    op.drop_table('incidents')
