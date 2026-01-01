"""
Simple JSON-based compliance store for demo persistence.

Stores compliance records per matter_id for later retrieval.
File-based storage for simplicity - not intended for production scale.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from nomoros_ai.models.compliance import StoredComplianceRecord

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = "./data/compliance_store.json"


def _get_store_path() -> Path:
    """Get the compliance store file path from env or default."""
    path_str = os.environ.get("COMPLIANCE_STORE_PATH", DEFAULT_STORE_PATH)
    return Path(path_str)


def _ensure_store_exists() -> Path:
    """Ensure the store file and directory exist."""
    store_path = _get_store_path()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not store_path.exists():
        store_path.write_text("{}")
    
    return store_path


def _load_store() -> dict:
    """Load the entire store from disk."""
    store_path = _ensure_store_exists()
    try:
        content = store_path.read_text()
        return json.loads(content) if content.strip() else {}
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load compliance store: {e}")
        return {}


def _save_store(data: dict) -> None:
    """Save the entire store to disk."""
    store_path = _ensure_store_exists()
    try:
        store_path.write_text(json.dumps(data, indent=2, default=str))
    except IOError as e:
        logger.error(f"Failed to save compliance store: {e}")


def save_compliance_record(record: StoredComplianceRecord) -> bool:
    """
    Save a compliance record, keyed by matter_id.
    Overwrites any existing record for the same matter_id.
    """
    try:
        store = _load_store()
        store[record.matter_id] = record.model_dump(mode="json")
        _save_store(store)
        logger.info(f"Saved compliance record for matter {record.matter_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save compliance record: {e}")
        return False


def get_compliance_record(matter_id: str) -> Optional[StoredComplianceRecord]:
    """
    Retrieve a compliance record by matter_id.
    Returns None if not found.
    """
    try:
        store = _load_store()
        record_data = store.get(matter_id)
        if record_data:
            return StoredComplianceRecord.model_validate(record_data)
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve compliance record: {e}")
        return None


def list_matter_ids() -> list[str]:
    """List all matter_ids in the store."""
    try:
        store = _load_store()
        return list(store.keys())
    except Exception as e:
        logger.error(f"Failed to list matter IDs: {e}")
        return []


def delete_compliance_record(matter_id: str) -> bool:
    """Delete a compliance record by matter_id."""
    try:
        store = _load_store()
        if matter_id in store:
            del store[matter_id]
            _save_store(store)
            logger.info(f"Deleted compliance record for matter {matter_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete compliance record: {e}")
        return False
