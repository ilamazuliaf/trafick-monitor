"""
Interfaces Route Module (prd.md Section 27)
Exposes GET /api/interfaces returning monitored interface states and live rates.
"""
from fastapi import APIRouter
from app.core.config import settings
from app.database.models import InterfacesResponse, InterfaceItem
from app.mikrotik.collector import collector

router = APIRouter(prefix="/api", tags=["Interfaces"])


@router.get("/interfaces", response_model=InterfacesResponse)
def get_interfaces():
    """
    Returns configured monitored interfaces and their live RX/TX rates.
    """
    items = []
    for iface_name in settings.monitored_interfaces:
        if iface_name in collector.latest_interfaces_status:
            items.append(collector.latest_interfaces_status[iface_name])
        else:
            items.append(InterfaceItem(
                name=iface_name,
                status="unknown",
                rx_bps=0.0,
                tx_bps=0.0
            ))

    return InterfacesResponse(interfaces=items)
