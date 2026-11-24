"""economics: crop-cycle expenses and harvest/sales (FR10)

Revision ID: 0008
Revises: 0007
Additive only: two new tables. Downgrade drops only these two tables.
Create Date: 2026-11-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ('seed', 'fertilizer', 'pesticide', 'labour', 'machinery', 'irrigation', 'energy',
              'land_rent', 'transport', 'other')


def _common(table: str) -> list[sa.Column | sa.Constraint]:
    return [
        sa.Column('crop_cycle_id', sa.Uuid(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f(f'fk_{table}_created_by_users'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['crop_cycle_id'], ['crop_cycles.id'], name=op.f(f'fk_{table}_crop_cycle_id_crop_cycles'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f(f'pk_{table}')),
    ]


def upgrade() -> None:
    op.create_table('expenses',
    sa.Column('category', sa.Enum(*CATEGORIES, name='expense_category', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('amount_pkr', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('incurred_on', sa.Date(), nullable=False),
    *_common('expenses'),
    sa.CheckConstraint('amount_pkr > 0', name=op.f('ck_expenses_amount_positive')),
    )
    op.create_index('ix_expenses_cycle_date', 'expenses', ['crop_cycle_id', 'incurred_on'], unique=False)
    op.create_table('harvest_sales',
    sa.Column('recorded_on', sa.Date(), nullable=False),
    sa.Column('quantity_kg', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('price_pkr_per_kg', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('buyer', sa.String(length=120), nullable=True),
    *_common('harvest_sales'),
    sa.CheckConstraint('quantity_kg > 0', name=op.f('ck_harvest_sales_quantity_positive')),
    sa.CheckConstraint('price_pkr_per_kg IS NULL OR price_pkr_per_kg >= 0', name=op.f('ck_harvest_sales_price_non_negative')),
    )
    op.create_index('ix_harvest_sales_cycle_date', 'harvest_sales', ['crop_cycle_id', 'recorded_on'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_harvest_sales_cycle_date', table_name='harvest_sales')
    op.drop_table('harvest_sales')
    op.drop_index('ix_expenses_cycle_date', table_name='expenses')
    op.drop_table('expenses')
