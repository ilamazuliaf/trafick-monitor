"""
Unit tests for OLT Monitor business logic (PRD Section 12.1)
"""
import asyncio
from unittest.mock import AsyncMock
from app.olt.config import OLTConfig
from app.olt.monitor import OLTMonitor


def test_olt_monitor_disabled():
    async def run():
        config = OLTConfig(enabled=False)
        mock_snmp = AsyncMock()
        monitor = OLTMonitor(config, mock_snmp)

        connected, msg, latency = await monitor.check_connection()
        assert connected is False
        assert "tidak aktif" in msg

        onts = await monitor.get_all_onts()
        assert onts == []

    asyncio.run(run())


def test_olt_monitor_filtering():
    async def run():
        config = OLTConfig(
            enabled=True,
            olt_name="OLT-UTAMA",
            olt_host="192.168.88.2",
            oid_ont_status="1.3.6.1.4.1.50224.3.3.2.1.8",
            oid_ont_rx_power="1.3.6.1.4.1.50224.3.3.3.1.4",
            rx_power_threshold=-25.0,
        )

        mock_snmp = AsyncMock()
        mock_snmp.walk.side_effect = lambda oid: {
            "1.3.6.1.4.1.50224.3.3.2.1.8.16777473": "INTEGER: 1", # online
            "1.3.6.1.4.1.50224.3.3.2.1.8.16777474": "INTEGER: 2", # offline
            "1.3.6.1.4.1.50224.3.3.2.1.8.16777475": "INTEGER: 1", # online
        } if oid == config.oid_ont_status else (
            {
                "1.3.6.1.4.1.50224.3.3.3.1.4.16777473.0.0": "INTEGER: -2400", # -24.0 (good)
                "1.3.6.1.4.1.50224.3.3.3.1.4.16777474.0.0": "INTEGER: -2650", # -26.5 (high atten & offline)
                "1.3.6.1.4.1.50224.3.3.3.1.4.16777475.0.0": "INTEGER: -2550", # -25.5 (high atten & online)
            } if oid == config.oid_ont_rx_power else {}
        )

        monitor = OLTMonitor(config, mock_snmp)

        offline = await monitor.get_offline_onts()
        assert len(offline) == 1
        assert offline[0].ont_id == "2"

        high_atten = await monitor.get_high_attenuation_onts()
        assert len(high_atten) == 2
        assert {ont.ont_id for ont in high_atten} == {"2", "3"}

    asyncio.run(run())
