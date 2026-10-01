"""
Traffic Service Module (prd.md Section 28)
Encapsulates business logic for validating parameters and retrieving traffic data.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.core.config import settings
from app.core.duration import parse_duration_seconds
from app.database.repository import TrafficRepository
from app.database.models import TrafficQueryResponse, InterfaceTrafficData


class TrafficService:

    @staticmethod
    def get_traffic_data(interface_name: str, period: str) -> TrafficQueryResponse:
        """
        Validates interface and period, queries database within time window,
        and returns downsampled traffic points.
        """
        # 1. Validate Interface (prd.md Section 28 + All Interfaces support)
        is_all = (interface_name.lower() == "all")
        if not is_all and interface_name not in settings.monitored_interfaces:
            raise ValueError(
                f"Interface '{interface_name}' is not in monitored interfaces list: {settings.monitored_interfaces}"
            )

        # 2. Validate Period (prd.md Section 28 & 14)
        period_seconds = parse_duration_seconds(period)

        # 3. Calculate Time Window
        now_dt = datetime.now(timezone.utc)
        start_dt = now_dt - timedelta(seconds=period_seconds)

        start_iso = start_dt.isoformat()
        end_iso = now_dt.isoformat()

        # 4. Fetch Traffic Points from SQLite Repository
        if is_all:
            # Aggregate total points for backward compatibility in data
            total_points = TrafficRepository.get_traffic_points(
                interface_name="all",
                start_iso=start_iso,
                end_iso=end_iso,
                max_points=settings.graph_max_points
            )
            # Fetch per-interface individual points
            iface_points_map = TrafficRepository.get_traffic_points_by_interface(
                interface_names=settings.monitored_interfaces,
                start_iso=start_iso,
                end_iso=end_iso,
                max_points=settings.graph_max_points
            )
            interfaces_data = [
                InterfaceTrafficData(name=iface_name, data=pts)
                for iface_name, pts in iface_points_map.items()
            ]

            return TrafficQueryResponse(
                interface=interface_name,
                period=period,
                data=total_points,
                interfaces=interfaces_data
            )
        else:
            points = TrafficRepository.get_traffic_points(
                interface_name=interface_name,
                start_iso=start_iso,
                end_iso=end_iso,
                max_points=settings.graph_max_points
            )
            return TrafficQueryResponse(
                interface=interface_name,
                period=period,
                data=points
            )

