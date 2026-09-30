"""
Duration Parser Unit Tests (prd.md Section 45)
"""
import pytest
from app.core.duration import parse_duration_seconds, format_duration_label


def test_valid_durations():
    assert parse_duration_seconds("1m") == 60
    assert parse_duration_seconds("5m") == 300
    assert parse_duration_seconds("15m") == 900
    assert parse_duration_seconds("30m") == 1800
    assert parse_duration_seconds("1h") == 3600
    assert parse_duration_seconds("2h") == 7200
    assert parse_duration_seconds("12h") == 43200
    assert parse_duration_seconds("24h") == 86400
    assert parse_duration_seconds("1d") == 86400
    assert parse_duration_seconds("2d") == 172800
    assert parse_duration_seconds("7d") == 604800
    assert parse_duration_seconds("30d") == 2592000


def test_invalid_durations():
    invalid_cases = ["5", "abc", "5x", "1minute", "1hour", "m", "h", "d", "-5m", "0m"]
    for case in invalid_cases:
        with pytest.raises(ValueError):
            parse_duration_seconds(case)


def test_duration_labels():
    assert format_duration_label("5m") == "5 Menit"
    assert format_duration_label("15m") == "15 Menit"
    assert format_duration_label("1h") == "1 Jam"
    assert format_duration_label("2h") == "2 Jam"
    assert format_duration_label("1d") == "1 Hari"
    assert format_duration_label("7d") == "7 Hari"
