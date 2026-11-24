"""knowledge sources register + full-text chunks (FR8 retrieval v1)

Revision ID: 0010
Revises: 0009
Additive only: two new tables (no data). Downgrade drops only these tables.
Create Date: 2026-11-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


def upgrade() -> None:
    op.create_table('knowledge_sources',
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('publisher', sa.String(length=200), nullable=False),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('url', sa.String(length=500), nullable=True),
    sa.Column('licence', sa.String(length=120), nullable=False),
    sa.Column('licence_url', sa.String(length=500), nullable=True),
    sa.Column('commercial_use', _enum('commercial_use', 'allowed', 'not_allowed', 'unknown'), nullable=False),
    sa.Column('attribution', sa.Text(), nullable=True),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('region', sa.String(length=80), nullable=True),
    sa.Column('review_status', _enum('source_review', 'unverified', 'licence_verified', 'content_reviewed', 'blocked'), nullable=False),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_sources')),
    )
    op.create_table('knowledge_chunks',
    sa.Column('source_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', coalesce(section, '') || ' ' || text)", persisted=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['knowledge_sources.id'], name=op.f('fk_knowledge_chunks_source_id_knowledge_sources'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_chunks')),
    )
    op.create_index('ix_knowledge_chunks_tsv', 'knowledge_chunks', ['tsv'], unique=False, postgresql_using='gin')
    op.create_index('ix_knowledge_chunks_source', 'knowledge_chunks', ['source_id', 'position'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_source', table_name='knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_tsv', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_sources')
