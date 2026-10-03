"""
OLT Monitoring Business Logic Module (PRD Section 8.5)
"""
import asyncio
from typing import List, Tuple
from app.olt.config import OLTConfig
from app.olt.models import ONT
from app.olt.snmp.client import SNMPClient
from app.olt.snmp.parser import parse_ont_table


class OLTMonitor:
    """
    Business logic coordinator for OLT monitoring operations.
    """

    def __init__(self, config: OLTConfig, snmp_client: SNMPClient):
        self.config = config
        self.snmp_client = snmp_client

    async def check_connection(self) -> Tuple[bool, str, float]:
        """
        Proxies connection check to SNMP client.
        (PRD Section 8.5)
        """
        if not self.config.enabled:
            return False, "Modul OLT tidak aktif (OLT_ENABLED=false)", 0.0
        return await self.snmp_client.check_connection()

    async def get_all_onts(self) -> List[ONT]:
        """
        Fetches all ONTs from OLT via SNMP WALK.
        (PRD Section 8.5)
        """
        if not self.config.enabled or not self.config.oid_ont_status:
            return []

        # Perform SNMP WALKs concurrently for configured OIDs
        tasks = {
            "status": self.snmp_client.walk(self.config.oid_ont_status),
        }
        if self.config.oid_ont_rx_power:
            tasks["rx_power"] = self.snmp_client.walk(self.config.oid_ont_rx_power)
        if self.config.oid_ont_tx_power:
            tasks["tx_power"] = self.snmp_client.walk(self.config.oid_ont_tx_power)
        if self.config.oid_ont_vendor:
            tasks["vendor"] = self.snmp_client.walk(self.config.oid_ont_vendor)
        if self.config.oid_ont_model:
            tasks["model"] = self.snmp_client.walk(self.config.oid_ont_model)
        if self.config.oid_ont_serial:
            tasks["serial"] = self.snmp_client.walk(self.config.oid_ont_serial)
        if self.config.oid_ont_name:
            tasks["name"] = self.snmp_client.walk(self.config.oid_ont_name)

        keys = list(tasks.keys())
        results = await asyncio.gather(*[tasks[k] for k in keys], return_exceptions=True)

        res_map = {}
        for idx, k in enumerate(keys):
            res = results[idx]
            if isinstance(res, dict):
                res_map[k] = res
            else:
                res_map[k] = {}

        status_map = res_map.get("status", {})
        rx_power_map = res_map.get("rx_power", {})
        tx_power_map = res_map.get("tx_power", {})
        vendor_map = res_map.get("vendor", {})
        model_map = res_map.get("model", {})
        serial_map = res_map.get("serial", {})
        name_map = res_map.get("name", {})

        onts = parse_ont_table(
            status_map=status_map,
            rx_power_map=rx_power_map,
            tx_power_map=tx_power_map,
            vendor_map=vendor_map,
            model_map=model_map,
            serial_map=serial_map,
            name_map=name_map,
            config=self.config,
        )

        onts.sort(key=lambda ont: ont.sort_key())
        return onts

    async def get_offline_onts(self) -> List[ONT]:
        """
        Returns list of offline ONTs, sorted by sort_key.
        (PRD Section 8.5)
        """
        all_onts = await self.get_all_onts()
        return [ont for ont in all_onts if ont.is_offline]

    async def get_high_attenuation_onts(self) -> List[ONT]:
        """
        Returns list of ONTs with rx_power <= threshold, sorted by sort_key.
        (PRD Section 8.5)
        """
        all_onts = await self.get_all_onts()
        threshold = self.config.rx_power_threshold
        return [ont for ont in all_onts if ont.rx_power is not None and ont.rx_power <= threshold]
