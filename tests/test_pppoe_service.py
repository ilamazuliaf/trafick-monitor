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


def test_pppoe_check_mikrotik_error_no_false_offline():
    CustomerRepository.create_customer(CustomerCreate(username="user01", customer_name="User 1"))

    mock_client = MagicMock()
    mock_client.host = "192.168.1.1"
    mock_client.port = 8728
    mock_client.get_active_pppoe.side_effect = MikrotikAPIError("Connection timeout")

    result = get_offline_customers(client=mock_client)
    assert result["status"] == "mikrotik_error"

    report = format_cek_off_report(result)
    assert "GAGAL MENGECEK PPPoE" in report
    assert "MikroTik tidak dapat dihubungi" in report
    assert "192.168.1.1:8728" in report
