"""expert reviews for Crop Doctor cases (FR12)

Revision ID: 0009
Revises: 0008
Additive only: one new table. Downgrade drops only this table.
Create Date: 2026-11-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DECISIONS = ('confirmed_model', 'diagnosed', 'needs_retake', 'cannot_determine', 'not_supported')


def upgrade() -> None:
    op.create_table('expert_reviews',
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('expert_id', sa.Uuid(), nullable=False),
    sa.Column('decision', sa.Enum(*DECISIONS, name='review_decision', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("decision NOT IN ('confirmed_model', 'diagnosed') OR label IS NOT NULL", name=op.f('ck_expert_reviews_label_required')),
    sa.ForeignKeyConstraint(['case_id'], ['diagnosis_cases.id'], name=op.f('fk_expert_reviews_case_id_diagnosis_cases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['expert_id'], ['users.id'], name=op.f('fk_expert_reviews_expert_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_expert_reviews')),
    )
    op.create_index('ix_expert_reviews_case', 'expert_reviews', ['case_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_expert_reviews_case', table_name='expert_reviews')
    op.drop_table('expert_reviews')
