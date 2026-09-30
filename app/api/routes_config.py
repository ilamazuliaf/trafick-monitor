"""
Config Route Module (prd.md Section 19)
Exposes GET /api/config endpoint for frontend initialization.
"""
from fastapi import APIRouter
from typing import Dict, Any

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["Configuration"])


@router.get("/config", response_model=Dict[str, Any])
def get_config():
    """
    Returns public application configuration driven strictly by .env
    """
    return settings.to_api_config()
