"""
PPPoE Monitoring Service Module (tambah_fitur.md Section 7, 21-26, 28)
Handles fetching active PPPoE sessions from MikroTik and comparing with monitored customers in SQLite database.
"""
import ipaddress
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.mikrotik.client import MikrotikClient, MikrotikAPIError
from app.database.repository import CustomerRepository
from app.database.models import CustomerRead
from app.core.config import settings
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


def get_isolated_customers(client: Optional[MikrotikClient] = None) -> Dict[str, Any]:
    """
    Fetches active RouterOS PPPoE sessions and identifies sessions whose IP address
    falls within settings.isolated_ip_range (e.g. 10.127.0.0/18).
    Enriches isolated sessions with customer details from database if available.
    """
    isolated_range_str = settings.isolated_ip_range.strip()
    try:
        isolated_network = ipaddress.ip_network(isolated_range_str, strict=False)
    except ValueError as e:
        logger.error(f"Invalid ISOLATED_IP_RANGE configuration '{isolated_range_str}': {e}")
        return {
            "status": "config_error",
            "message": f"⚠️ KONFIGURASI ISOLATED_IP_RANGE SALAH\n\nSubnet '{isolated_range_str}' tidak valid."
        }

    close_client = False
    if client is None:
        client = MikrotikClient()
        close_client = True

    try:
        active_sessions = client.get_active_pppoe_sessions()
    except Exception as e:
        logger.error(f"MikroTik connection/query failed during isolated check: {e}")
        return {
            "status": "mikrotik_error",
            "host": f"{client.host}:{client.port}",
            "error": str(e),
            "message": (
                "⚠️ GAGAL MENGECEK PPPoE ISOLIR\n\n"
                "MikroTik tidak dapat dihubungi.\n\n"
                f"Host:\n{client.host}:{client.port}\n\n"
                "Status:\nConnection failed"
            )
        }
    finally:
        if close_client and client:
            client.close()

    isolated_sessions = []
    for session in active_sessions:
        addr_str = session.get("address", "")
        if not addr_str:
            continue
        try:
            ip_obj = ipaddress.ip_address(addr_str)
            if ip_obj in isolated_network:
                username = session.get("name", "")
                cust = CustomerRepository.get_customer_by_username(username)
                isolated_sessions.append({
                    "username": username,
                    "address": addr_str,
                    "uptime": session.get("uptime", ""),
                    "customer_code": cust.customer_code if cust else None,
                    "customer_name": cust.customer_name if cust else username,
                    "package": cust.package if cust else "-",
                    "phone": cust.phone if cust else "-"
                })
        except ValueError:
            continue

    return {
        "status": "ok",
        "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "isolated_range": isolated_range_str,
        "total_isolated": len(isolated_sessions),
        "isolated_sessions": isolated_sessions
    }


def format_cek_isolir_report(report: Dict[str, Any]) -> str:
    """
    Formats isolated customers report dictionary into Telegram string representation.
    """
    status = report.get("status")
    if status == "config_error":
        return report.get("message", "⚠️ KONFIGURASI ISOLATED_IP_RANGE SALAH")
    if status == "mikrotik_error":
        return report.get("message", "⚠️ GAGAL MENGECEK PPPoE ISOLIR")

    total = report.get("total_isolated", 0)
    isolated_range = report.get("isolated_range", settings.isolated_ip_range)
    timestamp = report.get("timestamp", datetime.now().strftime("%d-%m-%Y %H:%M"))
    sessions = report.get("isolated_sessions", [])

    if total == 0:
        return (
            "🟢 TIDAK ADA PELANGGAN DI-ISOLIR\n\n"
            f"Waktu: {timestamp}\n"
            f"Subnet Isolir: {isolated_range}\n\n"
            f"Total Terisolir : 0 pelanggan\n\n"
            "Tidak ditemukan pelanggan PPPoE yang mendapat IP isolir."
        )

    lines = [
        "🟡 PPPoE ISOLIR\n",
        f"Waktu: {timestamp}",
        f"Subnet Isolir: {isolated_range}\n",
        f"Total Terisolir: {total} pelanggan\n",
        "Daftar Pelanggan Isolir:\n"
    ]

    for idx, sess in enumerate(sessions, start=1):
        code_str = f"{sess['customer_code']}" if sess.get('customer_code') else f"No.{idx}"
        lines.append(f"{idx}. {code_str}")
        lines.append(f"   Username : {sess['username']}")
        lines.append(f"   Nama     : {sess['customer_name']}")
        lines.append(f"   IP       : {sess['address']}")
        lines.append(f"   Paket    : {sess['package']}\n")

    lines.append(f"Total Terisolir: {total} pelanggan")
    return "\n".join(lines)


def get_unregistered_active_customers(client: Optional[MikrotikClient] = None) -> Dict[str, Any]:
    """
    Fetches active RouterOS PPPoE sessions from /ppp/active/print and compares them
    against all registered customers in the database.
    Identifies active sessions in MikroTik that are NOT found in the database.
    """
    db_customers = CustomerRepository.get_customers()
    db_usernames = {
        c.username.strip().lower()
        for c in db_customers
        if c.username and c.username.strip()
    }

    close_client = False
    if client is None:
        client = MikrotikClient()
        close_client = True

    try:
        active_sessions = client.get_active_pppoe_sessions()
    except Exception as e:
        logger.error(f"MikroTik connection/query failed during active ppp check: {e}")
        return {
            "status": "mikrotik_error",
            "host": f"{client.host}:{client.port}",
            "error": str(e),
            "message": (
                "⚠️ GAGAL MENGECEK DATA PELANGGAN\n\n"
                "MikroTik tidak dapat dihubungi.\n\n"
                f"Host:\n{client.host}:{client.port}\n\n"
                "Status:\nConnection failed"
            )
        }
    finally:
        if close_client and client:
            client.close()

    unregistered_sessions = [
        sess for sess in active_sessions
        if sess.get("name", "").strip().lower() not in db_usernames
    ]

    total_active = len(active_sessions)
    total_db = len(db_customers)
    unregistered_count = len(unregistered_sessions)
    registered_active_count = total_active - unregistered_count

    return {
        "status": "ok",
        "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "total_active": total_active,
        "total_db": total_db,
        "registered_active_count": registered_active_count,
        "unregistered_count": unregistered_count,
        "unregistered_sessions": unregistered_sessions
    }


def format_cek_pelanggan_report(report: Dict[str, Any], max_length: int = 3800) -> List[str]:
    """
    Formats unregistered active customer report into Telegram messages with pagination if needed.
    """
    status = report.get("status")
    if status == "mikrotik_error":
        return [report.get("message", "⚠️ GAGAL MENGECEK DATA PELANGGAN")]

    total_active = report.get("total_active", 0)
    total_db = report.get("total_db", 0)
    registered_active = report.get("registered_active_count", 0)
    unregistered_count = report.get("unregistered_count", 0)
    timestamp = report.get("timestamp", datetime.now().strftime("%d-%m-%Y %H:%M"))
    sessions = report.get("unregistered_sessions", [])

    if unregistered_count == 0:
        return [
            "🟢 SEMUA PELANGGAN AKTIF TERDAFTAR DI DATABASE\n\n"
            f"Waktu: {timestamp}\n\n"
            f"Total Aktif di MikroTik : {total_active}\n"
            f"Total di Database       : {total_db}\n"
            f"Aktif Terdaftar         : {registered_active}\n"
            f"Tidak Terdaftar         : 0\n\n"
            "Semua pelanggan yang aktif di MikroTik sudah terdata di database."
        ]

    header = (
        "⚠️ PELANGGAN AKTIF TIDAK TERDAFTAR DI DATABASE\n\n"
        f"Waktu: {timestamp}\n\n"
        f"Total Aktif di MikroTik : {total_active}\n"
        f"Total di Database       : {total_db}\n"
        f"Aktif Terdaftar         : {registered_active}\n"
        f"Tidak Terdaftar         : {unregistered_count}\n\n"
        "Daftar Pelanggan (Tidak ada di database):"
    )

    blocks: List[str] = []
    for idx, sess in enumerate(sessions, start=1):
        name = sess.get("name", "-")
        ip_addr = sess.get("address") or "-"
        caller_id = sess.get("caller_id") or "-"
        uptime = sess.get("uptime") or "-"
        service = sess.get("service") or "-"
        block = (
            f"{idx}. Username : {name}\n"
            f"   IP       : {ip_addr}\n"
            f"   Caller ID: {caller_id}\n"
            f"   Uptime   : {uptime}\n"
            f"   Service  : {service}"
        )
        blocks.append(block)

    footer = f"Total Tidak Terdaftar: {unregistered_count} pelanggan"

    # Paginate blocks
    pages_blocks: List[List[str]] = []
    current_page: List[str] = []
    current_len = len(header) + len(footer) + 10

    for block in blocks:
        block_len = len(block) + 2
        if current_page and (current_len + block_len > max_length):
            pages_blocks.append(current_page)
            current_page = [block]
            current_len = len(header) + len(footer) + 10 + block_len
        else:
            current_page.append(block)
            current_len += block_len

    if current_page:
        pages_blocks.append(current_page)

    total_pages = len(pages_blocks)
    if total_pages <= 1:
        content = "\n\n".join(pages_blocks[0]) if pages_blocks else ""
        return [f"{header}\n\n{content}\n\n{footer}"]

    result_messages: List[str] = []
    for idx, page in enumerate(pages_blocks, start=1):
        page_header = f"📄 Bagian {idx}/{total_pages}\n\n{header}"
        content = "\n\n".join(page)
        msg = f"{page_header}\n\n{content}\n\n{footer}"
        result_messages.append(msg)

    return result_messages


