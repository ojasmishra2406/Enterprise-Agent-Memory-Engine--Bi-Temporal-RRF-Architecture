from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("CREATE INDEX ix_memories_content_fts ON memories USING gin (to_tsvector('english', content));")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_content_fts;")
