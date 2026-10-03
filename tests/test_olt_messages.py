"""
Unit tests for OLT Message Formatters and Pagination (PRD Section 12.1)
"""
from app.olt.models import ONT
from app.olt.messages import (
    format_offline_onts_message,
    format_high_attenuation_message,
    format_olt_status_message,
    split_message,
)


def test_format_offline_onts_message():
    onts = [
        ONT(
            olt="OLT-UTAMA",
            slot="1",
            pon="1/1/1",
            ont_id="38",
            name="AMIR",
            status="offline",
            vendor="ZTE",
            model="F6639127",
        )
    ]
    messages = format_offline_onts_message(onts, "OLT-UTAMA", check_time="03-10-2026 02:30:15")
    assert len(messages) == 1
    assert "🔴 ONT PUTUS" in messages[0]
    assert "Total: 1 ONT" in messages[0]
    assert "PON 1/1/1" in messages[0]
    assert "AMIR" in messages[0]
    assert "ZTE F6639127" in messages[0]


def test_format_offline_onts_message_empty():
    messages = format_offline_onts_message([], "OLT-UTAMA", check_time="03-10-2026 02:30:15")
    assert len(messages) == 1
    assert "🟢 ONT PUTUS" in messages[0]
    assert "Tidak ada ONT yang putus" in messages[0]


def test_format_high_attenuation_message():
    onts = [
        ONT(
            olt="OLT-UTAMA",
            slot="1",
            pon="1/1/1",
            ont_id="2",
            name="TOLAK",
            status="online",
            vendor="GGCL",
            model="G6659127",
            rx_power=-25.52,
        )
    ]
    messages = format_high_attenuation_message(onts, "OLT-UTAMA", threshold=-25.0, check_time="03-10-2026 02:30:20")
    assert len(messages) == 1
    assert "⚠️ REDAMAN TINGGI" in messages[0]
    assert "Batas: -25.0 dBm" in messages[0]
    assert "RX Power: -25.52 dBm" in messages[0]


def test_format_olt_status_message():
    msg = format_olt_status_message(
        connected=True,
        message="CONNECTED",
        latency_ms=23.45,
        olt_name="OLT-UTAMA",
        host="192.168.88.2",
        version="2c",
        check_time="03-10-2026 02:30:25",
    )
    assert "📡 STATUS OLT MONITOR" in msg
    assert "🟢 CONNECTED" in msg
    assert "23.45 ms" in msg

    msg_err = format_olt_status_message(
        connected=False,
        message="ERROR (Timeout)",
        latency_ms=0.0,
        olt_name="OLT-UTAMA",
        host="192.168.88.2",
        version="2c",
        check_time="03-10-2026 02:30:25",
    )
    assert "🔴 ERROR (Timeout)" in msg_err


def test_split_message_pagination():
    header = "HEADER"
    footer = "FOOTER"
    blocks = [f"BLOCK_{i}" * 50 for i in range(20)]

    paginated = split_message(header, blocks, footer, max_length=500)
    assert len(paginated) > 1
    assert "📄 Bagian 1/" in paginated[0]
    assert "📄 Bagian 2/" in paginated[1]
