"""Add hospital emergency columns and dispatches table

Revision ID: 0003_hospitals_and_dispatches
Revises: 0002_incident_notes_and_expiry
Create Date: 2026-10-19 09:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0003_hospitals_and_dispatches'
down_revision: Union[str, None] = '0002_incident_notes_and_expiry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update hospitals table
    op.add_column(
        'hospitals',
        sa.Column('beds_simulated', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )
    op.add_column(
        'hospitals',
        sa.Column('emergency_types', postgresql.ARRAY(sa.String()), server_default=sa.text("ARRAY['general']::varchar[]"), nullable=False),
    )
    op.add_column(
        'hospitals',
        sa.Column('is_24x7', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'hospitals',
        sa.Column('source', sa.String(length=32), server_default='osm', nullable=False),
    )
    op.add_column(
        'hospitals',
        sa.Column('osm_attribution', sa.String(length=255), server_default='© OpenStreetMap contributors', nullable=False),
    )

    # 2. Create dispatch_status_enum
    dispatch_status_enum = postgresql.ENUM(
        'offered', 'accepted', 'en_route_to_scene', 'at_scene', 'to_hospital',
        'completed', 'declined', 'expired', 'cancelled',
        name='dispatch_status_enum',
        create_type=False,
    )
    dispatch_status_enum.create(op.get_bind(), checkfirst=True)

    # 3. Create dispatches table
    op.create_table(
        'dispatches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ambulance_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ambulances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hospital_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hospitals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', dispatch_status_enum, nullable=False),
        sa.Column('offered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('arrived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('picked_up_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('eta_to_scene_s', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('eta_to_hospital_s', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('emergency_type', sa.String(length=64), server_default='general', nullable=False),
        sa.Column('offer_number', sa.Integer(), server_default='1', nullable=False),
    )

    op.create_index(op.f('ix_dispatches_id'), 'dispatches', ['id'], unique=False)
    op.create_index(op.f('ix_dispatches_incident_id'), 'dispatches', ['incident_id'], unique=False)
    op.create_index(op.f('ix_dispatches_ambulance_id'), 'dispatches', ['ambulance_id'], unique=False)
    op.create_index(op.f('ix_dispatches_hospital_id'), 'dispatches', ['hospital_id'], unique=False)
    op.create_index(op.f('ix_dispatches_status'), 'dispatches', ['status'], unique=False)

    # Partial indexes for uniqueness on active dispatches
    op.create_index(
        'ix_dispatches_active_incident',
        'dispatches',
        ['incident_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('offered', 'accepted', 'en_route_to_scene', 'at_scene', 'to_hospital')"),
    )
    op.create_index(
        'ix_dispatches_active_ambulance',
        'dispatches',
        ['ambulance_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('accepted', 'en_route_to_scene', 'at_scene', 'to_hospital')"),
    )


def downgrade() -> None:
    op.drop_index('ix_dispatches_active_ambulance', table_name='dispatches')
    op.drop_index('ix_dispatches_active_incident', table_name='dispatches')
    op.drop_index(op.f('ix_dispatches_status'), table_name='dispatches')
    op.drop_index(op.f('ix_dispatches_hospital_id'), table_name='dispatches')
    op.drop_index(op.f('ix_dispatches_ambulance_id'), table_name='dispatches')
    op.drop_index(op.f('ix_dispatches_incident_id'), table_name='dispatches')
    op.drop_index(op.f('ix_dispatches_id'), table_name='dispatches')
    op.drop_table('dispatches')

    sa.Enum(name='dispatch_status_enum').drop(op.get_bind(), checkfirst=True)

    op.drop_column('hospitals', 'osm_attribution')
    op.drop_column('hospitals', 'source')
    op.drop_column('hospitals', 'is_24x7')
    op.drop_column('hospitals', 'emergency_types')
    op.drop_column('hospitals', 'beds_simulated')
