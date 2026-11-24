"""knowledge RAG: source provenance + ingestion state, chunk embeddings, conversations, queries

Revision ID: 0011
Revises: 0010
Additive only: new nullable/defaulted columns on knowledge_sources / knowledge_chunks and two
new tables. No existing row is changed except receiving column defaults. Downgrade drops only
what this revision added.
Create Date: 2026-11-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INGEST = ('not_ingested', 'queued', 'processing', 'indexed', 'failed')

def _source_cols() -> list[sa.Column]:
    return [
    sa.Column('author', sa.String(300), nullable=True),
    sa.Column('publication_date', sa.Date(), nullable=True),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('country', sa.String(80), nullable=True),
    sa.Column('domain', sa.String(40), nullable=True),
    sa.Column('crops', postgresql.ARRAY(sa.String(40)), server_default='{}', nullable=False),
    sa.Column('document_type', sa.String(40), nullable=True),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('file_key', sa.String(160), nullable=True),
    sa.Column('file_name', sa.String(255), nullable=True),
    sa.Column('file_mime', sa.String(100), nullable=True),
    sa.Column('file_bytes', sa.Integer(), nullable=True),
    sa.Column('file_sha256', sa.String(64), nullable=True),
    sa.Column('ingest_status', sa.Enum(*INGEST, name='ingest_status', native_enum=False,
              create_constraint=True, length=32), server_default='not_ingested', nullable=False),
    sa.Column('ingest_error', sa.Text(), nullable=True),
    sa.Column('ingest_log', postgresql.JSONB(), server_default='[]', nullable=False),
    sa.Column('chunk_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verified_by', sa.Uuid(), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    ]


def _chunk_cols() -> list[sa.Column]:
    return [
    sa.Column('embedding', postgresql.ARRAY(postgresql.REAL()), nullable=True),
    sa.Column('embedding_model', sa.String(120), nullable=True),
    sa.Column('content_hash', sa.String(64), nullable=True),
    sa.Column('language', sa.String(8), nullable=True),
    sa.Column('source_version', sa.Integer(), server_default='1', nullable=False),
    ]


def upgrade() -> None:
    for c in _source_cols():
        op.add_column('knowledge_sources', c)
    op.create_foreign_key(op.f('fk_knowledge_sources_verified_by_users'), 'knowledge_sources',
                          'users', ['verified_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_knowledge_sources_created_by_users'), 'knowledge_sources',
                          'users', ['created_by'], ['id'], ondelete='SET NULL')
    # Duplicate detection: the same file bytes cannot be registered twice.
    op.create_index('uq_knowledge_sources_file_sha256', 'knowledge_sources', ['file_sha256'],
                    unique=True, postgresql_where=sa.text('file_sha256 IS NOT NULL'))
    for c in _chunk_cols():
        op.add_column('knowledge_chunks', c)

    op.create_table('knowledge_conversations',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_knowledge_conversations_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_conversations')),
    )
    op.create_index('ix_knowledge_conversations_user', 'knowledge_conversations', ['user_id', 'updated_at'])
    op.create_table('knowledge_queries',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=True),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('retrieval_query', sa.Text(), nullable=False),
    sa.Column('language', sa.String(8), nullable=False),
    sa.Column('domain', sa.String(40), nullable=True),
    sa.Column('crops', postgresql.ARRAY(sa.String(40)), server_default='{}', nullable=False),
    sa.Column('status', sa.String(20), nullable=False),
    sa.Column('answer', sa.Text(), nullable=True),
    sa.Column('citations', postgresql.JSONB(), server_default='[]', nullable=False),
    sa.Column('meta', postgresql.JSONB(), server_default='{}', nullable=False),
    sa.Column('n_passages', sa.Integer(), server_default='0', nullable=False),
    sa.Column('top_score', sa.Float(), nullable=True),
    sa.Column('retrieval_ms', sa.Integer(), server_default='0', nullable=False),
    sa.Column('total_ms', sa.Integer(), server_default='0', nullable=False),
    sa.Column('llm_provider', sa.String(40), nullable=True),
    sa.Column('llm_model', sa.String(120), nullable=True),
    sa.Column('prompt_tokens', sa.Integer(), nullable=True),
    sa.Column('completion_tokens', sa.Integer(), nullable=True),
    sa.Column('feedback_rating', sa.SmallInteger(), nullable=True),
    sa.Column('feedback_comment', sa.String(500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('answered','extractive','abstained','clarify','error')", name=op.f('ck_knowledge_queries_status')),
    sa.CheckConstraint('feedback_rating IN (-1, 1)', name=op.f('ck_knowledge_queries_feedback')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_knowledge_queries_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['conversation_id'], ['knowledge_conversations.id'], name=op.f('fk_knowledge_queries_conversation_id_knowledge_conversations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_queries')),
    )
    op.create_index('ix_knowledge_queries_user', 'knowledge_queries', ['user_id', 'created_at'])
    op.create_index('ix_knowledge_queries_conversation', 'knowledge_queries', ['conversation_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_knowledge_queries_conversation', table_name='knowledge_queries')
    op.drop_index('ix_knowledge_queries_user', table_name='knowledge_queries')
    op.drop_table('knowledge_queries')
    op.drop_index('ix_knowledge_conversations_user', table_name='knowledge_conversations')
    op.drop_table('knowledge_conversations')
    for c in _chunk_cols():
        op.drop_column('knowledge_chunks', c.name)
    op.drop_index('uq_knowledge_sources_file_sha256', table_name='knowledge_sources')
    op.drop_constraint(op.f('fk_knowledge_sources_created_by_users'), 'knowledge_sources', type_='foreignkey')
    op.drop_constraint(op.f('fk_knowledge_sources_verified_by_users'), 'knowledge_sources', type_='foreignkey')
    for c in _source_cols():
        op.drop_column('knowledge_sources', c.name)
