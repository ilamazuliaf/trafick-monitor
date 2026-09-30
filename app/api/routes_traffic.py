"""
Traffic Route Module (prd.md Section 28)
Exposes GET /api/traffic?interface=X&period=Y endpoint.
"""
from fastapi import APIRouter, Query, HTTPException, status
from app.database.models import TrafficQueryResponse
from app.services.traffic_service import TrafficService

router = APIRouter(prefix="/api", tags=["Traffic"])


@router.get("/traffic", response_model=TrafficQueryResponse)
def get_traffic(
    interface: str = Query(..., description="Monitored interface name"),
    period: str = Query(..., description="Duration string (e.g. 15m, 1h, 2d)")
):
    """
    Returns time series traffic data points for a specific interface and period.
    """
    try:
        return TrafficService.get_traffic_data(interface_name=interface, period=period)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching traffic data: {e}"
        )
