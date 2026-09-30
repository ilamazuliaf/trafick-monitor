"""
Status Route Module (prd.md Section 26)
Exposes GET /api/status endpoint showing MikroTik connectivity state.
"""
from fastapi import APIRouter
from app.database.models import StatusResponse
from app.mikrotik.collector import collector

router = APIRouter(prefix="/api", tags=["Status"])


@router.get("/status", response_model=StatusResponse)
def get_status():
    """
    Returns current application and MikroTik router status.
    """
    return StatusResponse(
        status="ok",
        mikrotik=collector.is_mikrotik_connected,
        last_poll=collector.last_poll_time
    )
