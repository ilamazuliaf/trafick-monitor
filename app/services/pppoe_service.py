"""
PPPoE Monitoring Service Module (tambah_fitur.md Section 7, 21-26, 28)
Handles fetching active PPPoE sessions from MikroTik and comparing with monitored customers in SQLite database.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.mikrotik.client import MikrotikClient, MikrotikAPIError
from app.database.repository import CustomerRepository
from app.database.models import CustomerRead
from app.core.logging import logger


def get_offline_customers(client: Optional[MikrotikClient] = None) -> Dict[str, Any]:
    """
    Fetches monitored customers (monitoring_enabled=1) and active RouterOS PPPoE sessions.
    Compares the two datasets and returns offline status report dict.
    (tambah_fitur.md Section 7 & 21)
    """
    monitored_customers = CustomerRepository.get_monitored_customers()
    if not monitored_customers:
        return {
            "status": "empty_db",
            "message": (
                "⚠️ DATABASE PELANGGAN KOSONG\n\n"
                "Belum terdapat pelanggan yang dapat diperiksa.\n\n"
                "Silakan upload data pelanggan melalui menu Data Pelanggan."
            )
        }

    close_client = False
    if client is None:
        client = MikrotikClient()
        close_client = True

    try:
        active_users = client.get_active_pppoe()
    except Exception as e:
        logger.error(f"MikroTik connection/query failed during PPPoE check: {e}")
        return {
            "status": "mikrotik_error",
            "host": f"{client.host}:{client.port}",
            "error": str(e),
            "message": (
                "⚠️ GAGAL MENGECEK PPPoE\n\n"
                "MikroTik tidak dapat dihubungi.\n\n"
                f"Host:\n{client.host}:{client.port}\n\n"
                "Status:\nConnection failed\n\n"
                "Data pelanggan TIDAK diubah."
            )
        }
    finally:
        if close_client and client:
            client.close()

    active_set = set(active_users)
    offline_customers: List[CustomerRead] = [
        customer for customer in monitored_customers
        if customer.username.strip() not in active_set
    ]

    total_monitored = len(monitored_customers)
    offline_count = len(offline_customers)
    online_count = total_monitored - offline_count

    return {
        "status": "ok",
        "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "total_monitored": total_monitored,
        "online_count": online_count,
        "offline_count": offline_count,
        "offline_customers": offline_customers
    }


def format_cek_off_report(report: Dict[str, Any]) -> str:
    """
    Formats report dictionary into human-readable Telegram string representation.
    (tambah_fitur.md Section 22, 23, 24, 25)
    """
    status = report.get("status")
    if status == "empty_db":
        return report.get("message", "⚠️ DATABASE PELANGGAN KOSONG")
    if status == "mikrotik_error":
        return report.get("message", "⚠️ GAGAL MENGECEK PPPoE")

    total = report.get("total_monitored", 0)
    online = report.get("online_count", 0)
    offline = report.get("offline_count", 0)
    timestamp = report.get("timestamp", datetime.now().strftime("%d-%m-%Y %H:%M"))
    offline_customers: List[CustomerRead] = report.get("offline_customers", [])

    if offline == 0:
        return (
            "🟢 SEMUA PELANGGAN ONLINE\n\n"
            f"Waktu: {timestamp}\n\n"
            f"Total pelanggan dipantau : {total}\n"
            f"Online                   : {online}\n"
            f"Offline                  : 0\n\n"
            "Tidak ditemukan pelanggan PPPoE yang OFF."
        )

    lines = [
        "🔴 PPPoE OFF\n",
        f"Waktu: {timestamp}\n",
        f"Total pelanggan dipantau : {total}",
        f"Online                   : {online}",
        f"Offline                  : {offline}\n",
        "Daftar Offline:\n"
    ]

    for idx, cust in enumerate(offline_customers, start=1):
        code_str = f"{cust.customer_code}" if cust.customer_code else f"No.{idx}"
        pkg_str = cust.package if cust.package else "-"
        lines.append(f"{idx}. {code_str}")
        lines.append(f"   Username : {cust.username}")
        lines.append(f"   Nama     : {cust.customer_name}")
        lines.append(f"   Paket    : {pkg_str}\n")

    lines.append(f"Total OFF: {offline} pelanggan")
    return "\n".join(lines)
