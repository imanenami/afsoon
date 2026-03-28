"""Security utils for FastAPI handlers."""

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY = os.environ.get("API_KEY", "defaultsecret")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def api_key_security(api_key_value: str = Depends(api_key_header)):
    """Validate the API key provided in the request header."""
    if api_key_value is None or not secrets.compare_digest(api_key_value, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key_value
