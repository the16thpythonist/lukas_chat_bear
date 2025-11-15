"""remove_job_id_unique_constraint_add_job_name

Revision ID: d6afc466f142
Revises: afdcfcbfd9ab
Create Date: 2025-10-28 21:27:22.287492+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6afc466f142'
down_revision = 'afdcfcbfd9ab'
branch_labels = None
depends_on = None


def upgrade():
    # Add job_name column
    with op.batch_alter_table('scheduled_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('job_name', sa.String(length=100), nullable=True))
        batch_op.create_index('ix_scheduled_tasks_job_name', ['job_name'], unique=False)

        # Drop unique constraint on job_id (SQLite requires table recreation)
        batch_op.drop_index('ix_scheduled_tasks_job_id')
        batch_op.create_index('ix_scheduled_tasks_job_id', ['job_id'], unique=False)


def downgrade():
    # Remove job_name column and restore unique constraint on job_id
    with op.batch_alter_table('scheduled_tasks', schema=None) as batch_op:
        batch_op.drop_index('ix_scheduled_tasks_job_name')
        batch_op.drop_column('job_name')

        # Restore unique constraint on job_id
        batch_op.drop_index('ix_scheduled_tasks_job_id')
        batch_op.create_index('ix_scheduled_tasks_job_id', ['job_id'], unique=True)
