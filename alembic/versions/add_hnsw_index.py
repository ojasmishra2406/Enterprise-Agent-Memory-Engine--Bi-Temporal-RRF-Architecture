"""add hnsw index

Revision ID: add_hnsw_index
Revises: 0002
Create Date: 2026-10-01 18:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'add_hnsw_index'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute('CREATE INDEX memories_embedding_idx ON memories USING hnsw (embedding vector_cosine_ops);')

def downgrade() -> None:
    op.execute('DROP INDEX memories_embedding_idx;')
