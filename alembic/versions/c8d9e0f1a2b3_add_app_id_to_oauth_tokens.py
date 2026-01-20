"""Add app_id to oauth_tokens

Revision ID: c8d9e0f1a2b3
Revises: 40a8b24534f0
Create Date: 2026-01-20 15:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = '40a8b24534f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add app_id column to oauth_tokens table and change unique constraint
    from (user_id, provider) to (user_id, app_id) for per-app token storage.
    """
    # 1. Add app_id column (nullable initially for backward compatibility)
    op.add_column('oauth_tokens', sa.Column('app_id', sa.String(100), nullable=True))
    
    # 2. Create index on app_id
    op.create_index('ix_oauth_tokens_app_id', 'oauth_tokens', ['app_id'])
    
    # 3. Drop old unique constraint
    op.drop_constraint('uq_user_provider', 'oauth_tokens', type_='unique')
    
    # 4. Create new unique constraint on (user_id, app_id)
    op.create_unique_constraint('uq_user_app', 'oauth_tokens', ['user_id', 'app_id'])


def downgrade() -> None:
    """Revert to provider-based token storage."""
    # 1. Drop new unique constraint
    op.drop_constraint('uq_user_app', 'oauth_tokens', type_='unique')
    
    # 2. Drop app_id index
    op.drop_index('ix_oauth_tokens_app_id', table_name='oauth_tokens')
    
    # 3. Drop app_id column
    op.drop_column('oauth_tokens', 'app_id')
    
    # 4. Recreate old unique constraint
    op.create_unique_constraint('uq_user_provider', 'oauth_tokens', ['user_id', 'provider'])
