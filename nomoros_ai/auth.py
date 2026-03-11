"""
API Key authentication for internal service-to-service calls.

This module provides a reusable FastAPI dependency that validates
requests using a secret API key passed in the x-api-key header.

Security notes:
- API key is read from environment at runtime (never hardcoded)
- Key comparison uses secrets.compare_digest to prevent timing attacks
- Invalid/missing keys return 401 with minimal information
"""

import os
import secrets
from typing import Optional
from fastapi import Header, HTTPException, status


def get_api_key() -> str:
    """
    Get the internal API key from environment.
    
    Returns:
        The API key string
        
    Raises:
        RuntimeError: If INTERNAL_API_KEY is not configured
    """
    api_key = os.getenv("INTERNAL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "INTERNAL_API_KEY environment variable is not set. "
            "Please configure this secret in Replit Secrets."
        )
    return api_key


async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="x-api-key")) -> str:
    """
    FastAPI dependency to verify the API key from request headers.
    
    Usage:
        @app.post("/endpoint")
        async def endpoint(api_key: str = Depends(verify_api_key)):
            ...
    
    Args:
        x_api_key: The API key from the x-api-key header
        
    Returns:
        The validated API key (for downstream use if needed)
        
    Raises:
        HTTPException: 401 if key is missing or invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    
    expected_key = get_api_key()
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    
    return x_api_key


def validate_api_key_configured() -> None:
    """
    Startup validation to ensure API key is configured.
    
    Call this during application startup to fail fast if
    the required secret is missing.
    
    Raises:
        RuntimeError: If INTERNAL_API_KEY is not set
    """
    api_key = os.getenv("INTERNAL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "INTERNAL_API_KEY environment variable is not set. "
            "Please configure this secret in Replit Secrets before starting the API."
        )
