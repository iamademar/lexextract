"""add_progress_and_status_to_statements

Revision ID: 393047aa24db
Revises: 07d3d067661f
Create Date: 2025-07-15 23:45:46.761603

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '393047aa24db'
down_revision = '07d3d067661f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add progress column (Integer, default 0)
    op.add_column('statements', sa.Column('progress', sa.Integer(), nullable=False, server_default='0'))
    
    # Add status column with CHECK constraint for allowed values
    op.add_column('statements', sa.Column('status', sa.String(), nullable=False, server_default='pending'))
    
    # Add CHECK constraint for status values
    op.create_check_constraint(
        'check_statement_status',
        'statements',
        "status IN ('pending', 'processing', 'completed', 'failed')"
    )


def downgrade() -> None:
    # Drop CHECK constraint first
    op.drop_constraint('check_statement_status', 'statements', type_='check')
    
    # Drop columns
    op.drop_column('statements', 'status')
    op.drop_column('statements', 'progress') 