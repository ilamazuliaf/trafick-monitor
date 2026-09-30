"""
Configuration Layer Unit Tests (prd.md Section 45)
"""
import pytest
from app.core.config import Settings


def test_interface_parsing():
    settings = Settings(
        MONITORED_INTERFACES="ether1-BAROKAH, ether2-BIZ, ether3-WAHED, ether1-BAROKAH"
    )
    assert settings.monitored_interfaces == ["ether1-BAROKAH", "ether2-BIZ", "ether3-WAHED"]


def test_period_parsing():
    settings = Settings(
        GRAPH_PERIODS="5m, 15m, 1h, 2d",
        GRAPH_DEFAULT_PERIOD="15m"
    )
    periods = [p["value"] for p in settings.graph_periods_parsed]
    assert periods == ["5m", "15m", "1h", "2d"]
    assert settings.graph_periods_parsed[0]["label"] == "5 Menit"
    assert settings.graph_periods_parsed[2]["label"] == "1 Jam"


def test_invalid_default_period():
    with pytest.raises(ValueError):
        Settings(
            GRAPH_PERIODS="5m, 30m, 1h",
            GRAPH_DEFAULT_PERIOD="15m"  # 15m not in graph_periods!
        )


def test_api_config_dict():
    settings = Settings()
    config_dict = settings.to_api_config()
    assert "interfaces" in config_dict
    assert "graph_periods" in config_dict
    assert "default_period" in config_dict
    assert "realtime_max" in config_dict
    assert "refresh_interval" in config_dict
    assert "max_points" in config_dict
    # Password MUST NOT be present in API config (prd.md Section 40)
    assert "password" not in str(config_dict).lower()
