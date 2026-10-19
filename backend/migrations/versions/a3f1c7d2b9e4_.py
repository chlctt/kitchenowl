"""Add tasks

Revision ID: a3f1c7d2b9e4
Revises: 0b10d67750be
Create Date: 2026-10-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f1c7d2b9e4'
down_revision = '0b10d67750be'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('household', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tasks_feature', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('tasks_only_assignee_can_complete', sa.Boolean(), server_default=sa.false(), nullable=False))

    op.create_table('task',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('recurring', sa.Boolean(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('repeat_every', sa.Integer(), nullable=True),
    sa.Column('repeat_unit', sa.String(length=16), nullable=True),
    sa.Column('rotation_mode', sa.String(length=16), nullable=False),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('last_done_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['assigned_to'], ['user.id'], name=op.f('fk_task_assigned_to_user')),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], name=op.f('fk_task_created_by_user')),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], name=op.f('fk_task_household_id_household')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_task'))
    )
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_assigned_to'), ['assigned_to'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_household_id'), ['household_id'], unique=False)

    op.create_table('task_participant',
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['task.id'], name=op.f('fk_task_participant_task_id_task')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_task_participant_user_id_user')),
    sa.PrimaryKeyConstraint('task_id', 'user_id', name=op.f('pk_task_participant'))
    )
    with op.batch_alter_table('task_participant', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_participant_user_id'), ['user_id'], unique=False)

    op.create_table('task_completion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('task_name', sa.String(length=128), nullable=False),
    sa.Column('done_by', sa.Integer(), nullable=True),
    sa.Column('done_at', sa.DateTime(), nullable=False),
    sa.Column('previous_assigned_to', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['done_by'], ['user.id'], name=op.f('fk_task_completion_done_by_user')),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], name=op.f('fk_task_completion_household_id_household')),
    sa.ForeignKeyConstraint(['task_id'], ['task.id'], name=op.f('fk_task_completion_task_id_task')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_task_completion'))
    )
    with op.batch_alter_table('task_completion', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_completion_household_id'), ['household_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_completion_task_id'), ['task_id'], unique=False)


def downgrade():
    with op.batch_alter_table('task_completion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_completion_task_id'))
        batch_op.drop_index(batch_op.f('ix_task_completion_household_id'))
    op.drop_table('task_completion')

    with op.batch_alter_table('task_participant', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_participant_user_id'))
    op.drop_table('task_participant')

    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_household_id'))
        batch_op.drop_index(batch_op.f('ix_task_assigned_to'))
    op.drop_table('task')

    with op.batch_alter_table('household', schema=None) as batch_op:
        batch_op.drop_column('tasks_only_assignee_can_complete')
        batch_op.drop_column('tasks_feature')
