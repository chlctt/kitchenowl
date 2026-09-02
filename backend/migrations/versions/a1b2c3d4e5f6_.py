"""Add assigned_to and due_date to shoppinglist_items

Revision ID: a1b2c3d4e5f6
Revises: 0b10d67750be
Create Date: 2026-09-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '0b10d67750be'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('shoppinglist_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assigned_to', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('due_date', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f('fk_shoppinglist_items_assigned_to_user'),
            'user', ['assigned_to'], ['id']
        )


def downgrade():
    with op.batch_alter_table('shoppinglist_items', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_shoppinglist_items_assigned_to_user'),
            type_='foreignkey'
        )
        batch_op.drop_column('due_date')
        batch_op.drop_column('assigned_to')
