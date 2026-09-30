from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    
    op.create_table('memories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.String(length=128), nullable=False),
        sa.Column('agent_id', sa.String(length=128), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('memory_type', sa.Enum('SEMANTIC', 'PREFERENCE', 'EPISODIC', 'PROCEDURAL', 'TASK', name='memorytype'), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1024), nullable=False),
        sa.Column('importance', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('source_provenance', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('temporal_state', sa.Enum('ACTIVE', 'SUPERSEDED', 'DELETED', name='temporalstate'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('superseded_by_id', sa.Uuid(), nullable=True),
        sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='check_confidence_range'),
        sa.CheckConstraint('importance >= 0.0 AND importance <= 1.0', name='check_importance_range'),
        sa.ForeignKeyConstraint(['superseded_by_id'], ['memories.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_memories_embedding_hnsw', 'memories', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 200}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_memories_tenant_agent_state', 'memories', ['tenant_id', 'agent_id', 'temporal_state'], unique=False)
    op.create_index(op.f('ix_memories_agent_id'), 'memories', ['agent_id'], unique=False)
    op.create_index(op.f('ix_memories_superseded_by_id'), 'memories', ['superseded_by_id'], unique=False)
    op.create_index(op.f('ix_memories_tenant_id'), 'memories', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_memories_valid_from'), 'memories', ['valid_from'], unique=False)

def downgrade() -> None:
    op.drop_table('memories')
    op.execute("DROP TYPE temporalstate;")
    op.execute("DROP TYPE memorytype;")
