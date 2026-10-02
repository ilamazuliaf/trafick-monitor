"""
Unit Tests for Customer Repository (tambah_fitur.md Section 50)
"""
import os
import pytest
import sqlite3
from app.database.database import init_db
from app.database.models import CustomerCreate, CustomerUpdate
from app.database.repository import CustomerRepository, backup_database


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_traffic.db")
    monkeypatch.setattr("app.core.config.settings.database_path", test_db)
    init_db()
    yield test_db


def test_create_and_get_customer():
    cust = CustomerCreate(
        customer_code="C001",
        username="faiz001",
        customer_name="Faizul",
        phone="081234567890",
        address="Kambingan",
        package="10M",
        monitoring_enabled=True,
        notes="Test note"
    )
    created = CustomerRepository.create_customer(cust)
    assert created.id is not None
    assert created.username == "faiz001"
    assert created.customer_name == "Faizul"

    fetched = CustomerRepository.get_customer_by_username("faiz001")
    assert fetched is not None
    assert fetched.customer_code == "C001"
    assert fetched.monitoring_enabled is True


def test_duplicate_username_constraint():
    cust1 = CustomerCreate(username="faiz001", customer_name="Faiz 1")
    CustomerRepository.create_customer(cust1)

    cust2 = CustomerCreate(username="faiz001", customer_name="Faiz 2")
    with pytest.raises(sqlite3.IntegrityError):
        CustomerRepository.create_customer(cust2)


def test_update_customer():
    cust = CustomerCreate(username="faiz001", customer_name="Faizul", package="10M")
    CustomerRepository.create_customer(cust)

    update_data = CustomerUpdate(customer_name="Faizul Amali", package="20M")
    updated = CustomerRepository.update_customer("faiz001", update_data)

    assert updated is not None
    assert updated.customer_name == "Faizul Amali"
    assert updated.package == "20M"


def test_upsert_customer():
    cust = CustomerCreate(username="user01", customer_name="User One")
    # First upsert -> insert (returns False)
    is_update = CustomerRepository.upsert_customer(cust)
    assert is_update is False

    # Second upsert -> update (returns True)
    cust_mod = CustomerCreate(username="user01", customer_name="User One Modified")
    is_update2 = CustomerRepository.upsert_customer(cust_mod)
    assert is_update2 is True

    fetched = CustomerRepository.get_customer_by_username("user01")
    assert fetched.customer_name == "User One Modified"


def test_get_monitored_customers():
    cust1 = CustomerCreate(username="u1", customer_name="User 1", monitoring_enabled=True)
    cust2 = CustomerCreate(username="u2", customer_name="User 2", monitoring_enabled=False)
    CustomerRepository.create_customer(cust1)
    CustomerRepository.create_customer(cust2)

    all_cust = CustomerRepository.get_customers()
    assert len(all_cust) == 2

    monitored = CustomerRepository.get_monitored_customers()
    assert len(monitored) == 1
    assert monitored[0].username == "u1"


def test_bulk_upsert_customers_transaction():
    customers = [
        CustomerCreate(customer_code="C1", username="u1", customer_name="Name 1"),
        CustomerCreate(customer_code="C2", username="u2", customer_name="Name 2"),
        CustomerCreate(customer_code="C3", username="u3", customer_name="Name 3")
    ]
    created, updated = CustomerRepository.bulk_upsert_customers(customers)
    assert created == 3
    assert updated == 0

    # Bulk upsert again with modifications
    customers_mod = [
        CustomerCreate(customer_code="C1", username="u1", customer_name="Name 1 Mod"),
        CustomerCreate(customer_code="C4", username="u4", customer_name="Name 4")
    ]
    created2, updated2 = CustomerRepository.bulk_upsert_customers(customers_mod)
    assert created2 == 1
    assert updated2 == 1


def test_backup_database(tmp_path, monkeypatch):
    test_db = str(tmp_path / "data" / "traffic.db")
    monkeypatch.setattr("app.core.config.settings.database_path", test_db)
    init_db()

    backup_path = backup_database()
    assert backup_path != ""
    assert os.path.exists(backup_path)
