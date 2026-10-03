"""
OLT Configuration Dataclass and Loader (PRD Section 7 & 8.1)
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import dotenv_values


@dataclass
class OLTConfig:
    enabled: bool = False
    olt_name: str = "OLT-UTAMA"
    olt_host: str = "192.168.88.2"
    olt_port: int = 161
    snmp_version: str = "2c"
    snmp_community: str = "public"
    snmp_timeout: float = 3.0
    snmp_retries: int = 1
    rx_power_threshold: float = -25.0
    rx_power_scale: float = 100.0
    oid_ont_status: str = ""
    oid_ont_rx_power: str = ""
    oid_ont_tx_power: str = ""
    oid_ont_serial: str = ""
    oid_ont_vendor: str = ""
    oid_ont_model: str = ""
    oid_ont_name: str = ""
    ont_status_online_values: List[str] = field(default_factory=lambda: ["1"])
    ont_status_offline_values: List[str] = field(default_factory=lambda: ["2"])

    def validate(self) -> None:
        """
        Validates OLT configuration when enabled.
        (PRD Section 7.2 & 16)
        """
        if self.enabled:
            if not self.olt_host or not self.olt_host.strip():
                raise ValueError("OLT_HOST wajib diisi jika OLT_ENABLED=true.")
            if not self.oid_ont_status or not self.oid_ont_status.strip():
                raise ValueError("OID_ONT_STATUS wajib diisi jika OLT_ENABLED=true.")

    @classmethod
    def load(cls, env_file: str = ".env") -> "OLTConfig":
        """
        Loads OLT configuration from environment variables / .env file.
        (PRD Section 7.1 & 8.1)
        """
        env_vars = {}
        if os.path.exists(env_file):
            try:
                env_vars = dotenv_values(env_file)
            except Exception:
                pass

        def get_val(key: str, default: str = "") -> str:
            val = os.getenv(key)
            if val is not None:
                return val.strip()
            val_env = env_vars.get(key)
            if val_env is not None:
                return str(val_env).strip()
            return default

        enabled_str = get_val("OLT_ENABLED", "false").lower()
        enabled = enabled_str in ("true", "1", "yes", "on")

        olt_name = get_val("OLT_NAME", "OLT-UTAMA")
        olt_host = get_val("OLT_HOST", "192.168.88.2")

        try:
            olt_port = int(get_val("OLT_PORT", "161"))
        except ValueError:
            olt_port = 161

        snmp_version = get_val("OLT_SNMP_VERSION", "2c")
        snmp_community = get_val("OLT_SNMP_COMMUNITY", "public")

        try:
            snmp_timeout = float(get_val("SNMP_TIMEOUT", "3.0"))
        except ValueError:
            snmp_timeout = 3.0

        try:
            snmp_retries = int(get_val("SNMP_RETRIES", "1"))
        except ValueError:
            snmp_retries = 1

        try:
            rx_power_threshold = float(get_val("OLT_RX_POWER_THRESHOLD", "-25.0"))
        except ValueError:
            rx_power_threshold = -25.0

        try:
            rx_power_scale = float(get_val("OLT_RX_POWER_SCALE", "100.0"))
        except ValueError:
            rx_power_scale = 100.0

        oid_ont_status = get_val("OID_ONT_STATUS", "")
        oid_ont_rx_power = get_val("OID_ONT_RX_POWER", "")
        oid_ont_tx_power = get_val("OID_ONT_TX_POWER", "")
        oid_ont_serial = get_val("OID_ONT_SERIAL", "")
        oid_ont_vendor = get_val("OID_ONT_VENDOR", "")
        oid_ont_model = get_val("OID_ONT_MODEL", "")
        oid_ont_name = get_val("OID_ONT_NAME", "")

        online_raw = get_val("ONT_STATUS_ONLINE_VALUES", "1")
        online_vals = [v.strip() for v in online_raw.split(",") if v.strip()] or ["1"]

        offline_raw = get_val("ONT_STATUS_OFFLINE_VALUES", "2")
        offline_vals = [v.strip() for v in offline_raw.split(",") if v.strip()] or ["2"]

        config = cls(
            enabled=enabled,
            olt_name=olt_name,
            olt_host=olt_host,
            olt_port=olt_port,
            snmp_version=snmp_version,
            snmp_community=snmp_community,
            snmp_timeout=snmp_timeout,
            snmp_retries=snmp_retries,
            rx_power_threshold=rx_power_threshold,
            rx_power_scale=rx_power_scale,
            oid_ont_status=oid_ont_status,
            oid_ont_rx_power=oid_ont_rx_power,
            oid_ont_tx_power=oid_ont_tx_power,
            oid_ont_serial=oid_ont_serial,
            oid_ont_vendor=oid_ont_vendor,
            oid_ont_model=oid_ont_model,
            oid_ont_name=oid_ont_name,
            ont_status_online_values=online_vals,
            ont_status_offline_values=offline_vals,
        )
        return config
