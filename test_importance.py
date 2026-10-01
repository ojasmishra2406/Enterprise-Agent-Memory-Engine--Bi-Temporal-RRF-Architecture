import uuid
from datetime import datetime, timezone
import psycopg2

conn = psycopg2.connect("dbname='memory_engine' user='user' host='localhost' password='password' port='5432'")
cur = conn.cursor()

# We will test if Importance dominates Vector Rank
test_tenant = "test_importance_bug"
agent_id = "agent_test"

# Delete any previous test data
cur.execute("DELETE FROM memories WHERE tenant_id = %s", (test_tenant,))

# A fake 1024-d embedding (just zeros) - we won't rely on real LLM embeddings for the exact vector rank, 
# wait, actually we NEED real embeddings so the vector search works correctly against the query.
