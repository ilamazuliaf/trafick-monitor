"""
Database Repository Unit Tests (prd.md Section 45)
"""
import os
import tempfile
from datetime import datetime, timezone, timedelta
import pytest

from app.core.config import settings
from app.database.database import init_db, get_db_connection
from app.database.repository import TrafficRepository
from app.database.models import TrafficSampleCreate


@pytest.fixture(autouse=True)
def setup_temp_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    monkeypatch.setattr(settings, "database_path", db_path)
    init_db()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


def test_insert_and_get_traffic():
    now = datetime.now(timezone.utc)
    ts_now = now.isoformat()
    ts_past = (now - timedelta(minutes=5)).isoformat()

    sample1 = TrafficSampleCreate(
        timestamp=ts_past,
        interface_name="ether1-BAROKAH",
        rx_bytes=10000,
        tx_bytes=2000,
        rx_bps=100000.0,
        tx_bps=20000.0
    )
    sample2 = TrafficSampleCreate(
        timestamp=ts_now,
        interface_name="ether1-BAROKAH",
        rx_bytes=20000,
        tx_bytes=4000,
        rx_bps=120000.0,
        tx_bps=25000.0
    )

    TrafficRepository.insert_sample(sample1)
    TrafficRepository.insert_sample(sample2)

    latest = TrafficRepository.get_latest_sample("ether1-BAROKAH")
    assert latest is not None
    assert latest.rx_bytes == 20000
    assert latest.rx_bps == 120000.0

    points = TrafficRepository.get_traffic_points(
        interface_name="ether1-BAROKAH",
        start_iso=(now - timedelta(minutes=10)).isoformat(),
        end_iso=(now + timedelta(minutes=1)).isoformat()
    )
    assert len(points) == 2
    assert points[0].rx_bps == 100000.0
    assert points[1].rx_bps == 120000.0


def test_downsampling():
    now = datetime.now(timezone.utc)
    for i in range(100):
        ts = (now - timedelta(seconds=100 - i)).isoformat()
        sample = TrafficSampleCreate(
            timestamp=ts,
            interface_name="ether1-BAROKAH",
            rx_bytes=i * 100,
            tx_bytes=i * 20,
            rx_bps=float(i * 10),
            tx_bps=float(i * 2)
        )
        TrafficRepository.insert_sample(sample)

    # Query with max_points = 10
    points = TrafficRepository.get_traffic_points(
        interface_name="ether1-BAROKAH",
        start_iso=(now - timedelta(seconds=200)).isoformat(),
        end_iso=(now + timedelta(seconds=10)).isoformat(),
        max_points=10
    )
    assert len(points) <= 10
