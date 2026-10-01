from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/memory_engine"
    REDIS_URL: str = "redis://redis:6379/0"
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    EXTRACTION_MODEL: str = "llama3.1:8b"
    EMBEDDING_MODEL: str = "bge-m3"
    EMBEDDING_DIMENSIONS: int = 1024
    SIMILARITY_THRESHOLD: float = 0.50
    CONTRADICTION_TOP_K: int = 5
    LLM_TIMEOUT_SECONDS: float = 300.0
    DECAY_RATE_PER_SECOND: float = 2.67e-7
    RRF_K: float = 60.0
    CANDIDATE_POOL_SIZE: int = 50

settings = Settings()
