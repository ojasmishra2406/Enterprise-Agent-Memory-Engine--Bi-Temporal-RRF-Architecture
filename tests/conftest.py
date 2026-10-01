import pytest
import pytest_asyncio
import os
import subprocess
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from httpx import AsyncClient
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:password@memory_engine_db:5432/memory_engine_test"
os.environ["POSTGRES_DB"] = "memory_engine_test"

from app.config import settings
from app.database import get_db
from app.main import app

def kill_connections_and_drop():
    try:
        conn = psycopg2.connect("dbname='memory_engine' user='user' host='memory_engine_db' password='password' port='5432'")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute('''
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'memory_engine_test'
            AND pid <> pg_backend_pid();
        ''')
        cur.execute("DROP DATABASE IF EXISTS memory_engine_test")
        cur.close()
        conn.close()
    except Exception:
        pass

def create_db():
    kill_connections_and_drop()
    conn = psycopg2.connect("dbname='memory_engine' user='user' host='memory_engine_db' password='password' port='5432'")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("CREATE DATABASE memory_engine_test")
    cur.close()
    conn.close()

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    create_db()
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    yield
    kill_connections_and_drop()

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    session = async_session()
    try:
        await session.execute(text("TRUNCATE TABLE memories CASCADE;"))
        await session.commit()
        yield session
    finally:
        try:
            await session.close()
        except Exception:
            pass
        try:
            await engine.dispose()
        except Exception:
            pass

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    from httpx import ASGITransport
    
    transport = ASGITransport(app=app)
    ac = AsyncClient(transport=transport, base_url="http://test")
    try:
        yield ac
    finally:
        try:
            await ac.aclose()
        except Exception:
            pass
        app.dependency_overrides.clear()
