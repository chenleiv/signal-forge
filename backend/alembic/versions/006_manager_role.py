"""users.role: add 'manager'

Revision ID: 006
Revises: 005
Create Date: 2026-09-26
"""
from alembic import op

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('ck_users_role', type_='check')
        batch.create_check_constraint('ck_users_role', "role IN ('admin', 'manager', 'analyst')")


def downgrade() -> None:
    # Managers become analysts: the old constraint does not allow 'manager'.
    op.execute("UPDATE users SET role = 'analyst' WHERE role = 'manager'")
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('ck_users_role', type_='check')
        batch.create_check_constraint('ck_users_role', "role IN ('admin', 'analyst')")
