from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# Hardcoded tenant lookup for PoC
API_KEYS = {
    "test_key_tenant_a": "user_123",
    "test_key_tenant_b": "user_456"
}

async def get_current_tenant(api_key: str = Security(api_key_header)) -> str:
    tenant_id = API_KEYS.get(api_key)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return tenant_id
