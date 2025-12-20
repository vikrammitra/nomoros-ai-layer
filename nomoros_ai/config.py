"""
Configuration module for Nomoros AI API.

Handles loading of environment variables for Azure Document Intelligence
and other service configurations.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Azure Document Intelligence requires:
    - AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: The endpoint URL for your Azure resource
    - AZURE_DOCUMENT_INTELLIGENCE_KEY: The API key for authentication
    """
    
    # Azure Document Intelligence configuration
    azure_document_intelligence_endpoint: Optional[str] = None
    azure_document_intelligence_key: Optional[str] = None
    
    # Azure OpenAI configuration (for Local Authority extraction)
    azure_openai_endpoint: Optional[str] = None
    azure_openai_key: Optional[str] = None  # Accepts AZURE_OPENAI_KEY
    azure_openai_api_key: Optional[str] = None  # Also accepts AZURE_OPENAI_API_KEY
    azure_openai_deployment: Optional[str] = None
    azure_openai_api_version: str = "2024-12-01-preview"
    
    # Application settings
    app_name: str = "Nomoros AI API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    @property
    def openai_key(self) -> Optional[str]:
        """Get OpenAI key from either env var name."""
        return self.azure_openai_api_key or self.azure_openai_key
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def validate_azure_credentials() -> tuple[bool, str]:
    """
    Validate that Azure Document Intelligence credentials are configured.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not settings.azure_document_intelligence_endpoint:
        return False, "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT environment variable is not set"
    
    if not settings.azure_document_intelligence_key:
        return False, "AZURE_DOCUMENT_INTELLIGENCE_KEY environment variable is not set"
    
    return True, ""
