"""soil secondary nutrients, micronutrients, CEC and per-measure lab methods

Revision ID: 0007
Revises: 0006
Adds nullable columns to soil_observations (existing rows keep NULL = not measured).
Downgrade drops only these columns.
Create Date: 2026-11-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    ('calcium_mg_kg', 8, 2),
    ('magnesium_mg_kg', 8, 2),
    ('sulfur_mg_kg', 8, 2),
    ('zinc_mg_kg', 7, 3),
    ('iron_mg_kg', 7, 3),
    ('boron_mg_kg', 7, 3),
    ('cec_cmol_kg', 6, 2),
]


def upgrade() -> None:
    for name, precision, scale in COLUMNS:
        op.add_column('soil_observations', sa.Column(name, sa.Numeric(precision=precision, scale=scale), nullable=True))
    op.add_column('soil_observations', sa.Column('nutrient_methods', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('soil_observations', 'nutrient_methods')
    for name, _, _ in reversed(COLUMNS):
        op.drop_column('soil_observations', name)
