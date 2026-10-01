"""
Pydantic Data Models (prd.md Section 19, 24, 26, 27, 28)
Defines internal models and API response contracts.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class TrafficSampleCreate(BaseModel):
    timestamp: str
    interface_name: str
    rx_bytes: int
    tx_bytes: int
    rx_bps: float
    tx_bps: float


class TrafficSampleRead(BaseModel):
    id: Optional[int] = None
    timestamp: str
    interface_name: str
    rx_bytes: int
    tx_bytes: int
    rx_bps: float
    tx_bps: float


class InterfaceItem(BaseModel):
    name: str
    status: str  # "running" / "up" / "down" / "unknown"
    rx_bps: float
    tx_bps: float


class InterfacesResponse(BaseModel):
    interfaces: List[InterfaceItem]


class StatusResponse(BaseModel):
    status: str  # "ok" / "error"
    mikrotik: bool
    last_poll: Optional[str] = None


class TrafficPoint(BaseModel):
    timestamp: str
    rx_bps: float
    tx_bps: float


class InterfaceTrafficData(BaseModel):
    name: str
    data: List[TrafficPoint]


class TrafficQueryResponse(BaseModel):
    interface: str
    period: str
    data: Optional[List[TrafficPoint]] = None
    interfaces: Optional[List[InterfaceTrafficData]] = None

