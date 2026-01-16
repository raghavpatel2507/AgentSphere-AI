"""Fresh start migration

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2025-12-19 12:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get database connection and inspector
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create Enums safely
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversation_status') THEN
            CREATE TYPE conversation_status AS ENUM ('ACTIVE', 'ARCHIVED', 'PENDING_APPROVAL');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_role') THEN
            CREATE TYPE message_role AS ENUM ('USER', 'ASSISTANT', 'SYSTEM', 'TOOL');
        END IF;
    END
    $$;
    """)

    # Create tenants table
    if 'tenants' not in existing_tables:
        op.create_table(
            'tenants',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('api_key', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_tenants_api_key'), 'tenants', ['api_key'], unique=True)
        op.create_index(op.f('ix_tenants_is_active'), 'tenants', ['is_active'], unique=False)

    # Create tenant_configs table
    if 'tenant_configs' not in existing_tables:
        op.create_table(
            'tenant_configs',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('tenant_id', sa.UUID(), nullable=False),
            sa.Column('config_key', sa.String(length=255), nullable=False),
            sa.Column('config_value', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_tenant_configs_tenant_id'), 'tenant_configs', ['tenant_id'], unique=False)

    # Create conversations table
    if 'conversations' not in existing_tables:
        op.create_table(
            'conversations',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('tenant_id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=False),
            sa.Column('thread_id', sa.String(), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=True),
            sa.Column('status', postgresql.ENUM('ACTIVE', 'ARCHIVED', 'PENDING_APPROVAL', name='conversation_status', create_type=False), nullable=False, server_default='ACTIVE'),
            sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_conversations_tenant_id'), 'conversations', ['tenant_id'], unique=False)
        op.create_index(op.f('ix_conversations_thread_id'), 'conversations', ['thread_id'], unique=True)
        op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)

    # Create messages table
    if 'messages' not in existing_tables:
        op.create_table(
            'messages',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('conversation_id', sa.UUID(), nullable=False),
            sa.Column('role', postgresql.ENUM('USER', 'ASSISTANT', 'SYSTEM', 'TOOL', name='message_role', create_type=False), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)

    # Insert default tenant
    op.execute("""
        INSERT INTO tenants (id, name, api_key, is_active, metadata, created_at, updated_at)
        VALUES (
            '00000000-0000-0000-0000-000000000001',
            'Default Tenant',
            'dev_api_key_12345',
            true,
            '{"environment": "development", "created_by": "alembic_migration"}'::json,
            now(),
            now()
        ) ON CONFLICT (api_key) DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_thread_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_tenant_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_index(op.f('ix_tenant_configs_tenant_id'), table_name='tenant_configs')
    op.drop_table('tenant_configs')
    op.drop_index(op.f('ix_tenants_is_active'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_api_key'), table_name='tenants')
    op.drop_table('tenants')
    
    op.execute("DROP TYPE message_role")
    op.execute("DROP TYPE conversation_status")
