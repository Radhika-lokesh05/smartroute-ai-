"""Add note, expiry_reason, resolved_at, resolved_by_id to incidents table

Revision ID: 0002_incident_notes_and_expiry
Revises: 0001_initial_schema
Create Date: 2026-10-19 00:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_incident_notes_and_expiry'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('incidents', sa.Column('note', sa.String(length=200), nullable=True))
    op.add_column('incidents', sa.Column('expiry_reason', sa.String(length=50), nullable=True))
    op.add_column('incidents', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'incidents',
        sa.Column('resolved_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index(op.f('ix_incidents_resolved_by_id'), 'incidents', ['resolved_by_id'], unique=False)
    op.create_index('idx_incidents_status_expires', 'incidents', ['status', 'expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_incidents_status_expires', table_name='incidents')
    op.drop_index(op.f('ix_incidents_resolved_by_id'), table_name='incidents')
    op.drop_column('incidents', 'resolved_by_id')
    op.drop_column('incidents', 'resolved_at')
    op.drop_column('incidents', 'expiry_reason')
    op.drop_column('incidents', 'note')
