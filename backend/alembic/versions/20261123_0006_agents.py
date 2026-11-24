"""agent runs, steps and approval-gated actions

Revision ID: 0006
Revises: 0005
Tables: agent_runs, agent_steps, agent_actions. Additive only (downgrade drops them).
Create Date: 2026-11-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


def _ts() -> list[sa.Column]:
    return [
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    ]


def _json() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table('agent_runs',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('farm_id', sa.Uuid(), nullable=True),
    sa.Column('field_id', sa.Uuid(), nullable=True),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('intent', sa.String(length=40), nullable=False),
    sa.Column('agents', _json(), nullable=False),
    sa.Column('status', _enum('agent_run_status', 'completed', 'partial', 'failed'), nullable=False),
    sa.Column('response', _json(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    *_ts(),
    sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], name=op.f('fk_agent_runs_farm_id_farms'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], name=op.f('fk_agent_runs_field_id_fields'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_agent_runs_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_runs'))
    )
    op.create_index('ix_agent_runs_user_created', 'agent_runs', ['user_id', 'created_at'], unique=False)

    op.create_table('agent_steps',
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('agent', sa.String(length=40), nullable=False),
    sa.Column('tool', sa.String(length=60), nullable=False),
    sa.Column('mode', sa.String(length=8), nullable=False),
    sa.Column('input', _json(), nullable=False),
    sa.Column('status', _enum('agent_step_status', 'ok', 'unavailable', 'error', 'timeout', 'denied', 'proposed'), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    *_ts(),
    sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], name=op.f('fk_agent_steps_run_id_agent_runs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_steps'))
    )
    op.create_index(op.f('ix_agent_steps_run_id'), 'agent_steps', ['run_id'], unique=False)

    op.create_table('agent_actions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('agent', sa.String(length=40), nullable=False),
    sa.Column('tool', sa.String(length=60), nullable=False),
    sa.Column('args', _json(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', _enum('agent_action_status', 'pending', 'approved', 'rejected', 'expired', 'executed', 'failed'), nullable=False),
    sa.Column('requested_by', sa.Uuid(), nullable=False),
    sa.Column('decided_by', sa.Uuid(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('executed_by', sa.Uuid(), nullable=True),
    sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('result', _json(), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    *_ts(),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], name=op.f('fk_agent_actions_decided_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['executed_by'], ['users.id'], name=op.f('fk_agent_actions_executed_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], name=op.f('fk_agent_actions_requested_by_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], name=op.f('fk_agent_actions_run_id_agent_runs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_agent_actions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_actions'))
    )
    op.create_index('ix_agent_actions_user_status', 'agent_actions', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_agent_actions_user_status', table_name='agent_actions')
    op.drop_table('agent_actions')
    op.drop_index(op.f('ix_agent_steps_run_id'), table_name='agent_steps')
    op.drop_table('agent_steps')
    op.drop_index('ix_agent_runs_user_created', table_name='agent_runs')
    op.drop_table('agent_runs')
