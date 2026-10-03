"""
Unit tests for OLT Parser and Optical Power Converter (PRD Section 12.1)
"""
from app.olt.config import OLTConfig
from app.olt.models import ONT
from app.olt.snmp.parser import (
    clean_string_val,
    extract_oid_suffix,
    parse_pon_and_ont_id,
    parse_optical_power,
    map_status,
    parse_ont_table,
)


def test_clean_string_val():
    assert clean_string_val('STRING: "AMIR"') == "AMIR"
    assert clean_string_val('INTEGER: 1') == "1"
    assert clean_string_val('  "SUBAIDI"  ') == "SUBAIDI"
    assert clean_string_val(None) == ""


def test_extract_oid_suffix():
    full_oid = "1.3.6.1.4.1.50224.3.3.2.1.8.16777473"
    root_oid = "1.3.6.1.4.1.50224.3.3.2.1.8"
    assert extract_oid_suffix(full_oid, root_oid) == "16777473"


def test_parse_pon_and_ont_id_packed_hsgq():
    # 16777473 = 0x01000101 -> Slot 1, PON 1, ONT 1
    slot, pon, ont_id = parse_pon_and_ont_id("16777473")
    assert slot == "1"
    assert pon == "1/1/1"
    assert ont_id == "1"

    # DDM suffix with trailing .0.0
    slot, pon, ont_id = parse_pon_and_ont_id("16777473.0.0")
    assert slot == "1"
    assert pon == "1/1/1"
    assert ont_id == "1"


def test_parse_pon_and_ont_id_dotted():
    slot, pon, ont_id = parse_pon_and_ont_id("1.2.38")
    assert slot == "1"
    assert pon == "1/2"
    assert ont_id == "38"


def test_parse_optical_power():
    assert parse_optical_power("INTEGER: -2958", scale=100.0) == -29.58
    assert parse_optical_power("-253", scale=10.0) == -25.3
    # Sentinel values return None
    assert parse_optical_power("-2147483648", scale=100.0) is None
    assert parse_optical_power("65535", scale=100.0) is None
    assert parse_optical_power("2147483647", scale=100.0) is None
    assert parse_optical_power("-999", scale=100.0) is None
    assert parse_optical_power("N/A", scale=100.0) is None


def test_map_status():
    assert map_status("INTEGER: 1", ["1"], ["2"]) == "online"
    assert map_status("2", ["1"], ["2"]) == "offline"
    assert map_status("99", ["1"], ["2"]) == "offline"


def test_parse_ont_table():
    config = OLTConfig(
        olt_name="OLT-TEST",
        oid_ont_status="1.3.6.1.4.1.50224.3.3.2.1.8",
        oid_ont_rx_power="1.3.6.1.4.1.50224.3.3.3.1.4",
        oid_ont_name="1.3.6.1.4.1.50224.3.3.2.1.2",
        oid_ont_vendor="1.3.6.1.4.1.50224.3.3.2.1.25",
        oid_ont_model="1.3.6.1.4.1.50224.3.3.2.1.26",
        rx_power_scale=100.0,
    )

    status_map = {
        "1.3.6.1.4.1.50224.3.3.2.1.8.16777473": "INTEGER: 1",
        "1.3.6.1.4.1.50224.3.3.2.1.8.16777474": "INTEGER: 2",
    }
    rx_power_map = {
        "1.3.6.1.4.1.50224.3.3.3.1.4.16777473.0.0": "INTEGER: -2552",
        "1.3.6.1.4.1.50224.3.3.3.1.4.16777474.0.0": "INTEGER: -2958",
    }
    name_map = {
        "1.3.6.1.4.1.50224.3.3.2.1.2.16777473": 'STRING: "TOLAK"',
        "1.3.6.1.4.1.50224.3.3.2.1.2.16777474": 'STRING: "AMIR"',
    }
    vendor_map = {
        "1.3.6.1.4.1.50224.3.3.2.1.25.16777473": 'STRING: "GGCL"',
        "1.3.6.1.4.1.50224.3.3.2.1.25.16777474": 'STRING: "ZTE"',
    }
    model_map = {
        "1.3.6.1.4.1.50224.3.3.2.1.26.16777473": 'STRING: "G6659127"',
        "1.3.6.1.4.1.50224.3.3.2.1.26.16777474": 'STRING: "F6639127"',
    }

    onts = parse_ont_table(
        status_map=status_map,
        rx_power_map=rx_power_map,
        name_map=name_map,
        vendor_map=vendor_map,
        model_map=model_map,
        config=config,
    )

    assert len(onts) == 2
    ont1, ont2 = onts[0], onts[1]

    assert ont1.ont_id == "1"
    assert ont1.name == "TOLAK"
    assert ont1.status == "online"
    assert ont1.rx_power == -25.52
    assert ont1.display_model == "GGCL G6659127"

    assert ont2.ont_id == "2"
    assert ont2.name == "AMIR"
    assert ont2.status == "offline"
    assert ont2.rx_power == -29.58
    assert ont2.display_model == "ZTE F6639127"
