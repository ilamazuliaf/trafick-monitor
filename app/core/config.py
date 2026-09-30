"""
Configuration Module (prd.md Section 7, 9, 14, 16, 18, 40, 51)
Single Source of Truth configuration layer backed by .env
"""
import os
from typing import List, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.duration import parse_duration_seconds, format_duration_label
from app.core.logging import logger


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # MikroTik Configuration
    mikrotik_host: str = Field(default="192.168.1.1", alias="MIKROTIK_HOST")
    mikrotik_port: int = Field(default=8728, alias="MIKROTIK_PORT")
    mikrotik_username: str = Field(default="monitor", alias="MIKROTIK_USERNAME")
    mikrotik_password: str = Field(default="password", alias="MIKROTIK_PASSWORD")
    mikrotik_use_ssl: bool = Field(default=False, alias="MIKROTIK_USE_SSL")
    mikrotik_verify_ssl: bool = Field(default=False, alias="MIKROTIK_VERIFY_SSL")

    # Interface Monitoring
    monitored_interfaces_raw: str = Field(
        default="ether1-BAROKAH,ether2-BIZ,ether3-WAHED",
        alias="MONITORED_INTERFACES"
    )

    # Polling & Server
    poll_interval: int = Field(default=5, alias="POLL_INTERVAL")
    database_path: str = Field(default="./data/traffic.db", alias="DATABASE_PATH")
    web_host: str = Field(default="0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(default=8080, alias="WEB_PORT")

    # Graph Configuration
    graph_periods_raw: str = Field(
        default="5m,15m,30m,1h,12h,24h",
        alias="GRAPH_PERIODS"
    )
    graph_default_period: str = Field(default="15m", alias="GRAPH_DEFAULT_PERIOD")
    graph_realtime_max: str = Field(default="30m", alias="GRAPH_REALTIME_MAX")
    graph_refresh_interval: int = Field(default=5000, alias="GRAPH_REFRESH_INTERVAL")
    graph_max_points: int = Field(default=500, alias="GRAPH_MAX_POINTS")

    # Data Retention
    data_retention: str = Field(default="30d", alias="DATA_RETENTION")

    # Dynamic Parsed Attributes
    monitored_interfaces: List[str] = Field(default_factory=list)
    graph_periods_parsed: List[Dict[str, str]] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """
        Runs validations and parses raw comma-separated lists upon initialization.
        """
        # 1. Parse MONITORED_INTERFACES (prd.md Section 9)
        raw_ifaces = self.monitored_interfaces_raw.split(",")
        parsed_ifaces: List[str] = []
        for iface in raw_ifaces:
            cleaned = iface.strip()
            if cleaned and cleaned not in parsed_ifaces:
                parsed_ifaces.append(cleaned)
        
        if not parsed_ifaces:
            raise ValueError("MONITORED_INTERFACES must contain at least one interface name.")
        self.monitored_interfaces = parsed_ifaces

        # 2. Parse & Validate GRAPH_PERIODS (prd.md Section 12, 14, 15)
        raw_periods = self.graph_periods_raw.split(",")
        periods_list: List[str] = []
        parsed_period_objs: List[Dict[str, str]] = []

        for p in raw_periods:
            cleaned = p.strip()
            if not cleaned:
                continue
            # Validate duration format via parser
            parse_duration_seconds(cleaned)
            if cleaned not in periods_list:
                periods_list.append(cleaned)
                parsed_period_objs.append({
                    "value": cleaned,
                    "label": format_duration_label(cleaned)
                })

        if not parsed_period_objs:
            raise ValueError("GRAPH_PERIODS must contain at least one valid duration period.")
        
        self.graph_periods_parsed = parsed_period_objs

        # 3. Validate GRAPH_DEFAULT_PERIOD (prd.md Section 16)
        cleaned_default = self.graph_default_period.strip()
        parse_duration_seconds(cleaned_default) # throws error if invalid format
        if cleaned_default not in periods_list:
            raise ValueError(
                f"GRAPH_DEFAULT_PERIOD '{cleaned_default}' is not included in GRAPH_PERIODS list ({periods_list})."
            )
        self.graph_default_period = cleaned_default

        # 4. Validate GRAPH_REALTIME_MAX & DATA_RETENTION
        parse_duration_seconds(self.graph_realtime_max)
        parse_duration_seconds(self.data_retention)

        logger.info("Configuration successfully loaded & validated from .env.")
        logger.info(f"Monitored Interfaces: {self.monitored_interfaces}")
        logger.info(f"Graph Periods: {[p['value'] for p in self.graph_periods_parsed]}")

    def to_api_config(self) -> Dict[str, Any]:
        """
        Returns public configuration object for GET /api/config
        Excludes sensitive credentials (prd.md Section 19 & 40).
        """
        return {
            "interfaces": self.monitored_interfaces,
            "graph_periods": self.graph_periods_parsed,
            "default_period": self.graph_default_period,
            "realtime_max": self.graph_realtime_max,
            "refresh_interval": self.graph_refresh_interval,
            "max_points": self.graph_max_points
        }


# Global Settings Singleton
try:
    settings = Settings()
except Exception as e:
    logger.critical(f"FATAL: Configuration validation failed during startup: {e}")
    raise e
