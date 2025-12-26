"""Add HITL requests, OAuth tokens, and soft delete support

Revision ID: b7f8a9c0d1e2
Revises: f08c2c086e1b
Create Date: 2025-12-26 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7f8a9c0d1e2'
down_revision: Union[str, None] = 'f08c2c086e1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create HITL status enum using raw SQL to handle existing type
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE hitl_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create hitl_requests table
    op.create_table(
        'hitl_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tool_name', sa.String(255), nullable=False),
        sa.Column('tool_args', postgresql.JSONB, nullable=False),
        sa.Column('server_name', sa.String(255), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', name='hitl_status', create_type=False), nullable=False, server_default='PENDING'),
        sa.Column('decision_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_hitl_requests_user_id', 'hitl_requests', ['user_id'])
    op.create_index('ix_hitl_requests_conversation_id', 'hitl_requests', ['conversation_id'])
    op.create_index('ix_hitl_requests_status', 'hitl_requests', ['status'])
    
    # Create oauth_tokens table
    op.create_table(
        'oauth_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service', sa.String(50), nullable=False),
        sa.Column('access_token', sa.Text, nullable=False),
        sa.Column('refresh_token', sa.Text, nullable=True),
        sa.Column('token_uri', sa.String(500), nullable=True),
        sa.Column('scopes', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'service', name='uq_user_service'),
    )
    op.create_index('ix_oauth_tokens_user_id', 'oauth_tokens', ['user_id'])
    
    # Add soft delete columns to conversations table
    op.add_column('conversations', sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('conversations', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_conversations_is_deleted', 'conversations', ['is_deleted'])
    
    # Add new columns to users table
    op.add_column('users', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('preferences', postgresql.JSONB, nullable=True, server_default='{}'))
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    op.create_foreign_key('fk_users_tenant_id', 'users', 'tenants', ['tenant_id'], ['id'])
    
    # Add disabled_tools column to mcp_server_configs table
    op.add_column('mcp_server_configs', sa.Column('disabled_tools', postgresql.JSONB, nullable=True, server_default='[]'))


def downgrade() -> None:
    # Remove disabled_tools column from mcp_server_configs
    op.drop_column('mcp_server_configs', 'disabled_tools')
    
    # Remove new columns from users table
    op.drop_constraint('fk_users_tenant_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_tenant_id', 'users')
    op.drop_column('users', 'preferences')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'tenant_id')
    
    # Remove soft delete columns from conversations table
    op.drop_index('ix_conversations_is_deleted', 'conversations')
    op.drop_column('conversations', 'deleted_at')
    op.drop_column('conversations', 'is_deleted')
    
    # Drop oauth_tokens table
    op.drop_index('ix_oauth_tokens_user_id', 'oauth_tokens')
    op.drop_table('oauth_tokens')
    
    # Drop hitl_requests table
    op.drop_index('ix_hitl_requests_status', 'hitl_requests')
    op.drop_index('ix_hitl_requests_conversation_id', 'hitl_requests')
    op.drop_index('ix_hitl_requests_user_id', 'hitl_requests')
    op.drop_table('hitl_requests')
    
    # Drop HITL status enum
    hitl_status = postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', name='hitl_status')
    hitl_status.drop(op.get_bind(), checkfirst=True)
