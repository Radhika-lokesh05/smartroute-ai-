"""Initial schema with PostGIS extension, users, ambulances, incidents, and hospitals

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-18 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable PostGIS extension first
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 2. Create Enums safely
    user_role_enum = postgresql.ENUM('civilian', 'ambulance', 'admin', name='user_role_enum', create_type=False)
    ambulance_status_enum = postgresql.ENUM('offline', 'available', 'busy', name='ambulance_status_enum', create_type=False)
    incident_type_enum = postgresql.ENUM('accident', 'blockage', 'hazard', name='incident_type_enum', create_type=False)
    incident_status_enum = postgresql.ENUM('pending', 'validated', 'resolved', 'expired', name='incident_status_enum', create_type=False)
    vote_type_enum = postgresql.ENUM('confirm', 'reject', name='vote_type_enum', create_type=False)

    user_role_enum.create(op.get_bind(), checkfirst=True)
    ambulance_status_enum.create(op.get_bind(), checkfirst=True)
    incident_type_enum.create(op.get_bind(), checkfirst=True)
    incident_status_enum.create(op.get_bind(), checkfirst=True)
    vote_type_enum.create(op.get_bind(), checkfirst=True)

    # 3. Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', user_role_enum, nullable=False, server_default='civilian'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 4. Create ambulances table
    op.create_table(
        'ambulances',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plate_number', sa.String(length=64), nullable=False),
        sa.Column('status', ambulance_status_enum, nullable=False, server_default='offline'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('last_location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography', spatial_index=False), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f('ix_ambulances_id'), 'ambulances', ['id'], unique=False)
    op.create_index(op.f('ix_ambulances_user_id'), 'ambulances', ['user_id'], unique=True)
    op.create_index(op.f('ix_ambulances_plate_number'), 'ambulances', ['plate_number'], unique=True)
    op.create_index('idx_ambulances_last_location', 'ambulances', ['last_location'], unique=False, postgresql_using='gist')

    # 5. Create incidents table
    op.create_table(
        'incidents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography', spatial_index=False), nullable=False),
        sa.Column('incident_type', incident_type_enum, nullable=False),
        sa.Column('status', incident_status_enum, nullable=False, server_default='pending'),
        sa.Column('confirmations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rejections', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('trust_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f('ix_incidents_id'), 'incidents', ['id'], unique=False)
    op.create_index(op.f('ix_incidents_reporter_id'), 'incidents', ['reporter_id'], unique=False)
    op.create_index('idx_incidents_location', 'incidents', ['location'], unique=False, postgresql_using='gist')

    # 6. Create incident_votes table
    op.create_table(
        'incident_votes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vote', vote_type_enum, nullable=False),
        sa.Column('voter_location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography', spatial_index=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('incident_id', 'user_id', name='uq_incident_user_vote'),
    )
    op.create_index(op.f('ix_incident_votes_id'), 'incident_votes', ['id'], unique=False)
    op.create_index(op.f('ix_incident_votes_incident_id'), 'incident_votes', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_votes_user_id'), 'incident_votes', ['user_id'], unique=False)
    op.create_index('idx_incident_votes_voter_location', 'incident_votes', ['voter_location'], unique=False, postgresql_using='gist')

    # 7. Create hospitals table
    op.create_table(
        'hospitals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography', spatial_index=False), nullable=False),
        sa.Column('phone', sa.String(length=64), nullable=True),
        sa.Column('address', sa.String(length=512), nullable=True),
        sa.Column('has_emergency', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('specialties', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('simulated_beds', sa.Integer(), nullable=False, server_default='0', comment='SIMULATED data: Estimated emergency bed capacity for demonstration'),
        sa.Column('osm_id', sa.String(length=64), nullable=True),
    )
    op.create_index(op.f('ix_hospitals_id'), 'hospitals', ['id'], unique=False)
    op.create_index(op.f('ix_hospitals_name'), 'hospitals', ['name'], unique=False)
    op.create_index(op.f('ix_hospitals_osm_id'), 'hospitals', ['osm_id'], unique=True)
    op.create_index('idx_hospitals_location', 'hospitals', ['location'], unique=False, postgresql_using='gist')


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_hospitals_location', table_name='hospitals')
    op.drop_table('hospitals')

    op.drop_index('idx_incident_votes_voter_location', table_name='incident_votes')
    op.drop_table('incident_votes')

    op.drop_index('idx_incidents_location', table_name='incidents')
    op.drop_table('incidents')

    op.drop_index('idx_ambulances_last_location', table_name='ambulances')
    op.drop_table('ambulances')

    op.drop_table('users')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS vote_type_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS incident_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS incident_type_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS ambulance_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS user_role_enum CASCADE")
