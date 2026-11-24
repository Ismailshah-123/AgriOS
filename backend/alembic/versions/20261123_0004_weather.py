"""weather snapshots

Revision ID: 0004
Revises: 0003
Tables: weather_snapshots (provider cache keyed by coarse location). Additive only.
Create Date: 2026-11-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('weather_snapshots',
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('latitude', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('longitude', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_weather_snapshots')),
    sa.UniqueConstraint('provider', 'latitude', 'longitude', name='uq_weather_snapshots_provider_location')
    )


def downgrade() -> None:
    op.drop_table('weather_snapshots')
