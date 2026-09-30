"""
Traffic Collector Worker Module (prd.md Section 21, 22, 23, 25)
Single background task that polls MikroTik, calculates BPS rate, handles counter resets,
and persists traffic samples to SQLite.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.core.duration import parse_duration_seconds
from app.core.logging import logger
from app.mikrotik.client import MikrotikClient
from app.database.repository import TrafficRepository
from app.database.models import TrafficSampleCreate, InterfaceItem


class TrafficCollector:
    """
    Singleton Collector managing polling state and counter rate calculations.
    """

    def __init__(self):
        self.is_running = False
        self.last_poll_time: Optional[str] = None
        self.is_mikrotik_connected = False
        self.previous_counters: Dict[str, Dict[str, Any]] = {}
        self.latest_interfaces_status: Dict[str, InterfaceItem] = {}
        self.retention_seconds = parse_duration_seconds(settings.data_retention)
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Starts background polling task."""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Traffic Collector started. Polling every {settings.poll_interval}s.")

    async def stop(self) -> None:
        """Stops background polling task gracefully."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Traffic Collector stopped.")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        purge_counter = 0
        while self.is_running:
            try:
                start_time = time.time()
                await self._do_poll()

                # Run database retention purge every 100 polling cycles
                purge_counter += 1
                if purge_counter >= 100:
                    purge_counter = 0
                    TrafficRepository.purge_old_samples(self.retention_seconds)

                elapsed = time.time() - start_time
                sleep_time = max(0.5, settings.poll_interval - elapsed)
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in traffic collector poll loop: {e}")
                await asyncio.sleep(settings.poll_interval)

    async def _do_poll(self) -> None:
        """Executes a single poll cycle to MikroTik."""
        # Execute blocking socket operation in thread pool to avoid blocking asyncio event loop
        loop = asyncio.get_running_loop()
        stats = await loop.run_in_executor(None, self._fetch_mikrotik_stats)

        now_iso = datetime.now(timezone.utc).isoformat()
        self.last_poll_time = now_iso

        if stats is None:
            self.is_mikrotik_connected = False
            # Update interfaces status to DOWN/Disconnected
            for iface in settings.monitored_interfaces:
                self.latest_interfaces_status[iface] = InterfaceItem(
                    name=iface,
                    status="down",
                    rx_bps=0.0,
                    tx_bps=0.0
                )
            return

        self.is_mikrotik_connected = True
        stats_map = {item["name"]: item for item in stats}

        now_ts = time.time()

        for iface_name in settings.monitored_interfaces:
            iface_data = stats_map.get(iface_name)

            if not iface_data:
                self.latest_interfaces_status[iface_name] = InterfaceItem(
                    name=iface_name,
                    status="down",
                    rx_bps=0.0,
                    tx_bps=0.0
                )
                continue

            current_rx = iface_data["rx_bytes"]
            current_tx = iface_data["tx_bytes"]
            status = iface_data.get("status", "running")

            prev = self.previous_counters.get(iface_name)

            rx_bps = 0.0
            tx_bps = 0.0

            if prev:
                delta_time = now_ts - prev["timestamp"]
                if delta_time > 0:
                    delta_rx = current_rx - prev["rx_bytes"]
                    delta_tx = current_tx - prev["tx_bytes"]

                    # Handling Counter Reset / Restart (prd.md Section 23)
                    if delta_rx < 0 or delta_tx < 0:
                        logger.warning(
                            f"Counter reset detected on {iface_name} "
                            f"(prev RX:{prev['rx_bytes']} -> cur RX:{current_rx}). Resetting baseline."
                        )
                        rx_bps = 0.0
                        tx_bps = 0.0
                    else:
                        rx_bps = max(0.0, (delta_rx * 8.0) / delta_time)
                        tx_bps = max(0.0, (delta_tx * 8.0) / delta_time)

            # Store previous counter state
            self.previous_counters[iface_name] = {
                "timestamp": now_ts,
                "rx_bytes": current_rx,
                "tx_bytes": current_tx
            }

            # Update latest interface status for API
            self.latest_interfaces_status[iface_name] = InterfaceItem(
                name=iface_name,
                status=status,
                rx_bps=round(rx_bps, 2),
                tx_bps=round(tx_bps, 2)
            )

            # Persist sample to database
            sample = TrafficSampleCreate(
                timestamp=now_iso,
                interface_name=iface_name,
                rx_bytes=current_rx,
                tx_bytes=current_tx,
                rx_bps=round(rx_bps, 2),
                tx_bps=round(tx_bps, 2)
            )
            TrafficRepository.insert_sample(sample)

    def _fetch_mikrotik_stats(self) -> Optional[List[Dict[str, Any]]]:
        """Synchronous fetch from MikroTik client."""
        client = MikrotikClient()
        try:
            return client.get_interface_stats()
        except Exception as e:
            logger.warning(f"Error fetching MikroTik stats: {e}")
            return None
        finally:
            client.close()


# Global Collector Singleton
collector = TrafficCollector()
