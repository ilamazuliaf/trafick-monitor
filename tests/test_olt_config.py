"""
Unit tests for OLT Configuration (PRD Section 12.1)
"""
import pytest
from app.olt.config import OLTConfig


def test_olt_config_defaults():
    config = OLTConfig()
    assert config.enabled is False
    assert config.olt_name == "OLT-UTAMA"
    assert config.olt_host == "192.168.88.2"
    assert config.olt_port == 161
    assert config.snmp_version == "2c"
    assert config.snmp_community == "public"
    assert config.rx_power_threshold == -25.0
    assert config.rx_power_scale == 100.0


def test_olt_config_load(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OLT_ENABLED=true\n"
        "OLT_NAME=OLT-TEST\n"
        "OLT_HOST=10.0.0.1\n"
        "OLT_PORT=1616\n"
        "OLT_RX_POWER_THRESHOLD=-27.5\n"
        "OID_ONT_STATUS=1.3.6.1.4.1.50224.3.3.2.1.8\n"
        "ONT_STATUS_ONLINE_VALUES=1,3\n"
    )
    
    config = OLTConfig.load(env_file=str(env_file))
    assert config.enabled is True
    assert config.olt_name == "OLT-TEST"
    assert config.olt_host == "10.0.0.1"
    assert config.olt_port == 1616
    assert config.rx_power_threshold == -27.5
    assert config.oid_ont_status == "1.3.6.1.4.1.50224.3.3.2.1.8"
    assert config.ont_status_online_values == ["1", "3"]


def test_olt_config_validation():
    config = OLTConfig(enabled=True, olt_host="", oid_ont_status="1.2.3")
    with pytest.raises(ValueError, match="OLT_HOST"):
        config.validate()

    config2 = OLTConfig(enabled=True, olt_host="192.168.1.1", oid_ont_status="")
    with pytest.raises(ValueError, match="OID_ONT_STATUS"):
        config2.validate()

    config3 = OLTConfig(enabled=True, olt_host="192.168.1.1", oid_ont_status="1.2.3")
    config3.validate()  # should not raise
