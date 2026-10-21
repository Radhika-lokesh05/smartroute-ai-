"""Add audit_log table and is_simulated columns to incidents and dispatches

Revision ID: 0004_audit_log_and_simulated
Revises: 0003_hospitals_and_dispatches
Create Date: 2026-10-19 11:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0004_audit_log_and_simulated'
down_revision: Union[str, None] = '0003_hospitals_and_dispatches'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_audit_log_id'), 'audit_log', ['id'], unique=False)
    op.create_index(op.f('ix_audit_log_actor_user_id'), 'audit_log', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_type'), 'audit_log', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'], unique=False)

    # 2. Add is_simulated to incidents
    op.add_column(
        'incidents',
        sa.Column('is_simulated', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    )
    op.create_index(op.f('ix_incidents_is_simulated'), 'incidents', ['is_simulated'], unique=False)

    # 3. Add is_simulated to dispatches
    op.add_column(
        'dispatches',
        sa.Column('is_simulated', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    )
    op.create_index(op.f('ix_dispatches_is_simulated'), 'dispatches', ['is_simulated'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dispatches_is_simulated'), table_name='dispatches')
    op.drop_column('dispatches', 'is_simulated')

    op.drop_index(op.f('ix_incidents_is_simulated'), table_name='incidents')
    op.drop_column('incidents', 'is_simulated')

    op.drop_index(op.f('ix_audit_log_created_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_entity_type'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_action'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_actor_user_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_id'), table_name='audit_log')
    op.drop_table('audit_log')
