"""add manager_decisions table and recommendation FK

Revision ID: a1b2c3d4e5f6
Revises: 639cb7baf8d8
Create Date: 2026-09-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '639cb7baf8d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('manager_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('decision_type', sa.String(length=100), nullable=False),
        sa.Column('request_context', sa.Text(), nullable=True),
        sa.Column('agents_consulted', sa.JSON(), nullable=True),
        sa.Column('agent_outputs', sa.JSON(), nullable=True),
        sa.Column('conflicts_detected', sa.JSON(), nullable=True),
        sa.Column('final_decision', sa.Text(), nullable=False),
        sa.Column('final_reasoning', sa.Text(), nullable=True),
        sa.Column('evidence_post_ids', sa.JSON(), nullable=True),
        sa.Column('evidence_memory_ids', sa.JSON(), nullable=True),
        sa.Column('metrics_considered', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['creator_id'], ['creators.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_decisions_creator_type', 'manager_decisions', ['creator_id', 'decision_type'])

    op.add_column('recommendations', sa.Column('manager_decision_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_recommendations_decision', 'recommendations', 'manager_decisions',
        ['manager_decision_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_recommendations_decision', 'recommendations', type_='foreignkey')
    op.drop_column('recommendations', 'manager_decision_id')
    op.drop_index('ix_decisions_creator_type', table_name='manager_decisions')
    op.drop_table('manager_decisions')
