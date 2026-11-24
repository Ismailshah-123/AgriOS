"""soil observations

Revision ID: 0005
Revises: 0004
Tables: soil_observations. Additive only.
Create Date: 2026-11-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


def upgrade() -> None:
    op.create_table('soil_observations',
    sa.Column('field_id', sa.Uuid(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('sampled_on', sa.Date(), nullable=False),
    sa.Column('data_origin', _enum('data_origin', 'measured', 'farmer_entered', 'retrieved', 'inferred', 'simulated'), nullable=False),
    sa.Column('lab_name', sa.String(length=120), nullable=True),
    sa.Column('lab_reference', sa.String(length=80), nullable=True),
    sa.Column('depth_from_cm', sa.Numeric(precision=5, scale=1), nullable=True),
    sa.Column('depth_to_cm', sa.Numeric(precision=5, scale=1), nullable=True),
    sa.Column('ph', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('ph_method', _enum('soil_ph_method', 'water_1_1', 'water_1_2_5', 'saturated_paste', 'cacl2', 'unknown'), nullable=False),
    sa.Column('ec_ds_m', sa.Numeric(precision=7, scale=3), nullable=True),
    sa.Column('ec_method', _enum('soil_ec_method', 'saturated_paste_ece', 'extract_1_1', 'extract_1_2_5', 'extract_1_5', 'unknown'), nullable=False),
    sa.Column('organic_matter_pct', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('organic_carbon_pct', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('nitrogen_total_pct', sa.Numeric(precision=6, scale=3), nullable=True),
    sa.Column('phosphorus_mg_kg', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('phosphorus_method', _enum('soil_p_method', 'olsen', 'bray_1', 'mehlich_3', 'unknown'), nullable=False),
    sa.Column('potassium_mg_kg', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('texture', _enum('soil_texture', 'sand', 'loamy_sand', 'sandy_loam', 'loam', 'silt_loam', 'silt', 'sandy_clay_loam', 'clay_loam', 'silty_clay_loam', 'sandy_clay', 'silty_clay', 'clay'), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('ph IS NULL OR (ph >= 0 AND ph <= 14)', name=op.f('ck_soil_observations_ph_range')),
    sa.CheckConstraint('ec_ds_m IS NULL OR (ec_ds_m >= 0 AND ec_ds_m <= 200)', name=op.f('ck_soil_observations_ec_range')),
    sa.CheckConstraint('organic_matter_pct IS NULL OR (organic_matter_pct >= 0 AND organic_matter_pct <= 100)', name=op.f('ck_soil_observations_om_range')),
    sa.CheckConstraint('organic_carbon_pct IS NULL OR (organic_carbon_pct >= 0 AND organic_carbon_pct <= 60)', name=op.f('ck_soil_observations_oc_range')),
    sa.CheckConstraint("data_origin IN ('measured', 'farmer_entered')", name=op.f('ck_soil_observations_origin_allowed')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_soil_observations_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], name=op.f('fk_soil_observations_field_id_fields'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_soil_observations'))
    )
    op.create_index('ix_soil_observations_field_date', 'soil_observations', ['field_id', 'sampled_on'], unique=False)
    op.create_index(op.f('ix_soil_observations_field_id'), 'soil_observations', ['field_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_soil_observations_field_id'), table_name='soil_observations')
    op.drop_index('ix_soil_observations_field_date', table_name='soil_observations')
    op.drop_table('soil_observations')
