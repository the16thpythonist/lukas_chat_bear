"""add_scheduled_events_table

Revision ID: 0134250f8b22
Revises: d6afc466f142
Create Date: 2025-10-29 19:46:14.425727+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0134250f8b22'
down_revision = 'd6afc466f142'
branch_labels = None
depends_on = None


def upgrade():
    # Create scheduled_events table
    op.create_table(
        'scheduled_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.String(50), nullable=False, server_default='channel_message'),
        sa.Column('scheduled_time', sa.DateTime(), nullable=False),
        sa.Column('target_channel_id', sa.String(255), nullable=False),
        sa.Column('target_channel_name', sa.String(255), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('job_id', sa.String(255), nullable=True, unique=True),
        sa.Column('created_by_user_id', sa.String(255), nullable=True),
        sa.Column('created_by_user_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True)
    )

    # Create indexes for common queries
    op.create_index('idx_scheduled_events_status', 'scheduled_events', ['status'])
    op.create_index('idx_scheduled_events_scheduled_time', 'scheduled_events', ['scheduled_time'])
    op.create_index('idx_scheduled_events_created_by', 'scheduled_events', ['created_by_user_id'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_scheduled_events_created_by', 'scheduled_events')
    op.drop_index('idx_scheduled_events_scheduled_time', 'scheduled_events')
    op.drop_index('idx_scheduled_events_status', 'scheduled_events')

    # Drop table
    op.drop_table('scheduled_events')
