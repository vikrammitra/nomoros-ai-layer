"""
Azure OpenAI client for assistive document extraction.

IMPORTANT: This service is used for EXTRACTION ONLY, not for:
- Making legal conclusions
- Assigning risk severity
- Final decision-making

All severity and risk decisions remain deterministic in the rules layer.
"""

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from nomoros_ai.config import settings

logger = logging.getLogger(__name__)


class AzureOpenAIConfig(BaseModel):
    """Configuration for Azure OpenAI service."""
    endpoint: str
    api_key: str
    deployment_name: str = "gpt-4o"  # Default to GPT-4o
    api_version: str = "2024-02-15-preview"


class AzureOpenAIClient:
    """
    Client for Azure OpenAI API calls.
    
    Used for assistive extraction from legal documents.
    Returns structured JSON only - no free-form text.
    """
    
    # Conservative settings for legal document processing
    TEMPERATURE = 0  # Deterministic output
    # Note: gpt-5-nano-2 is a reasoning model that uses internal reasoning tokens
    # before generating the response. We need enough tokens for both reasoning
    # and the actual JSON output. 16000 allows ~8000 reasoning + 8000 content.
    MAX_TOKENS = 16000
    TIMEOUT_SECONDS = 180
    MAX_RETRIES = 2
    
    def __init__(self, config: AzureOpenAIConfig | None = None):
        """
        Initialize client with config or environment variables.
        """
        if config:
            self.config = config
        else:
            self.config = self._load_from_env()
        
        self._client = httpx.Client(timeout=self.TIMEOUT_SECONDS)
    
    def _load_from_env(self) -> AzureOpenAIConfig:
        """Load configuration from centralized settings."""
        endpoint = settings.azure_openai_endpoint or ""
        api_key = settings.openai_key or ""  # Uses property that checks both env var names
        deployment = settings.azure_openai_deployment or "gpt-4o"
        api_version = settings.azure_openai_api_version
        
        return AzureOpenAIConfig(
            endpoint=endpoint,
            api_key=api_key,
            deployment_name=deployment,
            api_version=api_version
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if Azure OpenAI credentials are configured."""
        return bool(self.config.endpoint and self.config.api_key)
    
    def extract_structured(
        self,
        text_chunk: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Extract structured data from text using Azure OpenAI.
        
        Args:
            text_chunk: The text to analyze
            system_prompt: System message defining the task
            user_prompt: User message with specific instructions
            response_schema: Optional JSON schema for response validation
            
        Returns:
            Parsed JSON response from the model
            
        Raises:
            ValueError: If Azure OpenAI is not configured
            RuntimeError: If extraction fails after retries
        """
        if not self.is_configured:
            raise ValueError("Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.")
        
        # Build the API URL
        url = (
            f"{self.config.endpoint.rstrip('/')}/openai/deployments/"
            f"{self.config.deployment_name}/chat/completions"
            f"?api-version={self.config.api_version}"
        )
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_prompt}\n\nDocument text:\n{text_chunk}"}
        ]
        
        # Build request payload
        # Note: Newer models (gpt-5, o1, etc.) use max_completion_tokens instead of max_tokens
        # Note: Some models (o1, gpt-5-nano) don't support temperature parameter
        payload = {
            "messages": messages,
            "max_completion_tokens": self.MAX_TOKENS,
            "response_format": {"type": "json_object"}
        }
        
        headers = {
            "Content-Type": "application/json",
            "api-key": self.config.api_key
        }
        
        # Attempt extraction with retries
        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = self._client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                # Check if we have choices
                if not result.get("choices"):
                    logger.warning(f"No choices in Azure OpenAI response: {result}")
                    return {}
                
                message = result["choices"][0].get("message", {})
                content = message.get("content", "")
                
                # Check finish reason
                finish_reason = result["choices"][0].get("finish_reason", "unknown")
                if finish_reason != "stop":
                    logger.warning(f"Azure OpenAI finish_reason: {finish_reason}")
                
                # Handle empty or whitespace-only responses
                if not content or not content.strip():
                    logger.warning(f"Empty response from Azure OpenAI. Finish reason: {finish_reason}. Full response: {result}")
                    return {}
                
                # Parse and return JSON
                return json.loads(content)
                
            except httpx.HTTPStatusError as e:
                last_error = e
                # Log the full error response for debugging
                try:
                    error_body = e.response.text
                    logger.warning(f"Azure OpenAI HTTP error (attempt {attempt + 1}): {e}. Response: {error_body[:500]}")
                except:
                    logger.warning(f"Azure OpenAI HTTP error (attempt {attempt + 1}): {e}")
                if e.response.status_code == 429:
                    # Rate limited - wait before retry
                    import time
                    time.sleep(2 ** attempt)
                elif e.response.status_code >= 500:
                    # Server error - retry
                    continue
                else:
                    # Client error - don't retry
                    raise RuntimeError(f"Azure OpenAI request failed: {e}")
                    
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Azure OpenAI timeout (attempt {attempt + 1}): {e}")
                continue
                
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"Invalid JSON response (attempt {attempt + 1}): {e}")
                continue
        
        raise RuntimeError(f"Azure OpenAI extraction failed after {self.MAX_RETRIES + 1} attempts: {last_error}")
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
