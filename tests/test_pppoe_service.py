"""
Unit Tests for PPPoE Monitoring Service (tambah_fitur.md Section 50 & 51)
"""
import pytest
from unittest.mock import MagicMock
from app.database.database import init_db
from app.database.models import CustomerCreate
from app.database.repository import CustomerRepository
from app.services.pppoe_service import get_offline_customers, format_cek_off_report
from app.mikrotik.client import MikrotikAPIError


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_pppoe.db")
    monkeypatch.setattr("app.core.config.settings.database_path", test_db)
    init_db()
    yield test_db


def test_pppoe_check_empty_database():
    mock_client = MagicMock()
    result = get_offline_customers(client=mock_client)
    assert result["status"] == "empty_db"
    report = format_cek_off_report(result)
    assert "DATABASE PELANGGAN KOSONG" in report
    mock_client.get_active_pppoe.assert_not_called()


def test_pppoe_check_all_online():
    CustomerRepository.create_customer(CustomerCreate(username="user01", customer_name="User 1"))
    CustomerRepository.create_customer(CustomerCreate(username="user02", customer_name="User 2"))

    mock_client = MagicMock()
    mock_client.get_active_pppoe.return_value = ["user01", "user02", "user03"]

    result = get_offline_customers(client=mock_client)
    assert result["status"] == "ok"
    assert result["total_monitored"] == 2
    assert result["online_count"] == 2
    assert result["offline_count"] == 0
    assert len(result["offline_customers"]) == 0

    report = format_cek_off_report(result)
    assert "SEMUA PELANGGAN ONLINE" in report


def test_pppoe_check_some_offline():
    CustomerRepository.create_customer(CustomerCreate(customer_code="C001", username="user01", customer_name="User 1", package="10M"))
    CustomerRepository.create_customer(CustomerCreate(customer_code="C002", username="user02", customer_name="User 2", package="20M"))
    CustomerRepository.create_customer(CustomerCreate(customer_code="C003", username="user03", customer_name="User 3", package="10M"))
    # user04 disabled monitoring -> should be ignored
    CustomerRepository.create_customer(CustomerCreate(customer_code="C004", username="user04", customer_name="User 4", monitoring_enabled=False))

    mock_client = MagicMock()
    mock_client.get_active_pppoe.return_value = ["user01"]

    result = get_offline_customers(client=mock_client)
    assert result["status"] == "ok"
    assert result["total_monitored"] == 3  # user04 ignored
    assert result["online_count"] == 1
    assert result["offline_count"] == 2

    offline_users = [c.username for c in result["offline_customers"]]
    assert "user02" in offline_users
    assert "user03" in offline_users
    assert "user04" not in offline_users

    report = format_cek_off_report(result)
    assert "PPPoE OFF" in report
    assert "user02" in report
    assert "user03" in report


def test_pppoe_check_all_offline():
    CustomerRepository.create_customer(CustomerCreate(username="user01", customer_name="User 1"))
    CustomerRepository.create_customer(CustomerCreate(username="user02", customer_name="User 2"))

    mock_client = MagicMock()
    mock_client.get_active_pppoe.return_value = []

    result = get_offline_customers(client=mock_client)
    assert result["status"] == "ok"
    assert result["total_monitored"] == 2
    assert result["online_count"] == 0
    assert result["offline_count"] == 2


from app.services.pppoe_service import (
    get_offline_customers,
    format_cek_off_report,
    get_isolated_customers,
    format_cek_isolir_report
)


def test_pppoe_check_isolated_customers(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.isolated_ip_range", "10.127.0.0/18")
    CustomerRepository.create_customer(CustomerCreate(customer_code="C001", username="isolir01", customer_name="Isolir User 1", package="10M"))
    CustomerRepository.create_customer(CustomerCreate(customer_code="C002", username="normal01", customer_name="Normal User 1", package="20M"))

    mock_client = MagicMock()
    mock_client.get_active_pppoe_sessions.return_value = [
        {"name": "isolir01", "address": "10.127.0.15", "uptime": "1h"},  # In 10.127.0.0/18 -> Isolated!
        {"name": "normal01", "address": "10.10.10.20", "uptime": "2h"}   # Outside -> Normal
    ]

    result = get_isolated_customers(client=mock_client)
    assert result["status"] == "ok"
    assert result["total_isolated"] == 1
    assert result["isolated_sessions"][0]["username"] == "isolir01"
    assert result["isolated_sessions"][0]["address"] == "10.127.0.15"

    report = format_cek_isolir_report(result)
    assert "PPPoE ISOLIR" in report
    assert "isolir01" in report
    assert "10.127.0.15" in report


from app.services.pppoe_service import (
    get_unregistered_active_customers,
    format_cek_pelanggan_report
)


def test_unregistered_active_customers_all_registered():
    CustomerRepository.create_customer(CustomerCreate(username="user01", customer_name="User Satu"))
    CustomerRepository.create_customer(CustomerCreate(username="user02", customer_name="User Dua"))

    mock_client = MagicMock()
    mock_client.get_active_pppoe_sessions.return_value = [
        {"name": "user01", "address": "10.10.10.2", "caller_id": "aa:bb", "uptime": "1d", "service": "pppoe"},
        {"name": "user02", "address": "10.10.10.3", "caller_id": "cc:dd", "uptime": "2d", "service": "pppoe"}
    ]

    result = get_unregistered_active_customers(client=mock_client)
    assert result["status"] == "ok"
    assert result["total_active"] == 2
    assert result["total_db"] == 2
    assert result["registered_active_count"] == 2
    assert result["unregistered_count"] == 0
    assert len(result["unregistered_sessions"]) == 0

    report_msgs = format_cek_pelanggan_report(result)
    assert len(report_msgs) == 1
    assert "SEMUA PELANGGAN AKTIF TERDAFTAR DI DATABASE" in report_msgs[0]


def test_unregistered_active_customers_some_unregistered():
    CustomerRepository.create_customer(CustomerCreate(username="user01", customer_name="User Satu"))

    mock_client = MagicMock()
    mock_client.get_active_pppoe_sessions.return_value = [
        {"name": "user01", "address": "10.10.10.2", "caller_id": "aa:bb", "uptime": "1d", "service": "pppoe"},
        {"name": "unknown_user", "address": "10.10.10.99", "caller_id": "ee:ff", "uptime": "5m", "service": "pppoe"}
    ]

    result = get_unregistered_active_customers(client=mock_client)
    assert result["status"] == "ok"
    assert result["total_active"] == 2
    assert result["total_db"] == 1
    assert result["registered_active_count"] == 1
    assert result["unregistered_count"] == 1
    assert result["unregistered_sessions"][0]["name"] == "unknown_user"

    report_msgs = format_cek_pelanggan_report(result)
    assert len(report_msgs) == 1
    assert "PELANGGAN AKTIF TIDAK TERDAFTAR DI DATABASE" in report_msgs[0]
    assert "unknown_user" in report_msgs[0]
    assert "10.10.10.99" in report_msgs[0]


def test_unregistered_active_customers_mikrotik_error():
    mock_client = MagicMock()
    mock_client.get_active_pppoe_sessions.side_effect = Exception("Connection timed out")

    result = get_unregistered_active_customers(client=mock_client)
    assert result["status"] == "mikrotik_error"

    report_msgs = format_cek_pelanggan_report(result)
    assert len(report_msgs) == 1
    assert "GAGAL MENGECEK DATA PELANGGAN" in report_msgs[0]


