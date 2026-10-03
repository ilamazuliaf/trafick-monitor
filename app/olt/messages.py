"""
HTML & Text Message Formatters for OLT Telegram Bot (PRD Section 6.2, 6.3 & 8.7)
"""
from datetime import datetime
from typing import Dict, List, Optional
from app.olt.models import ONT


def get_current_timestamp() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")


def split_message(header: str, blocks: List[str], footer: str, max_length: int = 4000) -> List[str]:
    """
    Splits message into multiple paginated parts if total length exceeds Telegram max length.
    (PRD Section 6.3 & 8.7)
    """
    if not blocks:
        single_msg = f"{header}\n\n{footer}".strip()
        return [single_msg]

    pages_blocks: List[List[str]] = []
    current_page: List[str] = []
    current_len = len(header) + len(footer) + 10  # Margin for linebreaks

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
    if total_pages == 1:
        content = "\n\n".join(pages_blocks[0])
        return [f"{header}\n\n{content}\n\n{footer}"]

    result_messages: List[str] = []
    for idx, page in enumerate(pages_blocks, start=1):
        page_header = f"📄 Bagian {idx}/{total_pages}\n\n{header}"
        content = "\n\n".join(page)
        msg = f"{page_header}\n\n{content}\n\n{footer}"
        result_messages.append(msg)

    return result_messages


def format_offline_onts_message(
    onts: List[ONT], olt_name: str, check_time: Optional[str] = None
) -> List[str]:
    """
    Formats /cek_putus report grouped by PON port.
    (PRD Section 6.2 & 8.7)
    """
    t_str = check_time or get_current_timestamp()
    footer = f"⏱ Waktu pengecekan:\n{t_str}"

    if not onts:
        header = f"🟢 ONT PUTUS\n\nOLT: {olt_name}\nTotal: 0 ONT"
        body = "Tidak ada ONT yang putus (OFFLINE)."
        return split_message(header, [body], footer)

    header = f"🔴 ONT PUTUS\n\nOLT: {olt_name}\nTotal: {len(onts)} ONT"

    # Group by PON
    grouped: Dict[str, List[ONT]] = {}
    for ont in onts:
        pon_key = f"PON {ont.pon}"
        if pon_key not in grouped:
            grouped[pon_key] = []
        grouped[pon_key].append(ont)

    blocks: List[str] = []
    for pon_title, pon_onts in grouped.items():
        ont_lines = [pon_title]
        for ont in pon_onts:
            lines = [
                f"• ONT {ont.ont_id}",
                f"  Nama: {ont.name or '-'}",
                f"  Status: {ont.status.upper()}",
                f"  Model: {ont.display_model}",
            ]
            ont_lines.append("\n".join(lines))
        blocks.append("\n".join(ont_lines))

    return split_message(header, blocks, footer)


def format_high_attenuation_message(
    onts: List[ONT], olt_name: str, threshold: float, check_time: Optional[str] = None
) -> List[str]:
    """
    Formats /cek_redaman report grouped by PON port.
    (PRD Section 6.2 & 8.7)
    """
    t_str = check_time or get_current_timestamp()
    footer = f"⏱ Waktu pengecekan:\n{t_str}"
    thresh_str = f"{threshold:.1f}"

    if not onts:
        header = f"🟢 REDAMAN TINGGI\n\nOLT: {olt_name}\nBatas: {thresh_str} dBm\nTotal: 0 ONT"
        body = f"Tidak ada ONT dengan redaman tinggi (<= {thresh_str} dBm)."
        return split_message(header, [body], footer)

    header = f"⚠️ REDAMAN TINGGI\n\nOLT: {olt_name}\nBatas: {thresh_str} dBm\nTotal: {len(onts)} ONT"

    # Group by PON
    grouped: Dict[str, List[ONT]] = {}
    for ont in onts:
        pon_key = f"PON {ont.pon}"
        if pon_key not in grouped:
            grouped[pon_key] = []
        grouped[pon_key].append(ont)

    blocks: List[str] = []
    for pon_title, pon_onts in grouped.items():
        ont_lines = [pon_title]
        for ont in pon_onts:
            rx_str = f"{ont.rx_power:.2f} dBm" if ont.rx_power is not None else "-"
            lines = [
                f"• ONT {ont.ont_id}",
                f"  Nama: {ont.name or '-'}",
                f"  Model: {ont.display_model}",
                f"  RX Power: {rx_str}",
                f"  Status: {ont.status.upper()}",
            ]
            ont_lines.append("\n".join(lines))
        blocks.append("\n".join(ont_lines))

    return split_message(header, blocks, footer)


def format_olt_status_message(
    connected: bool,
    message: str,
    latency_ms: float,
    olt_name: str,
    host: str,
    version: str,
    check_time: Optional[str] = None,
) -> str:
    """
    Formats /olt_status message.
    (PRD Section 6.2 & 8.7)
    """
    t_str = check_time or get_current_timestamp()

    if connected:
        status_line = "Status: 🟢 CONNECTED"
        response_line = f"Response: {latency_ms:.2f} ms\n"
    else:
        status_line = f"Status: 🔴 {message}"
        response_line = ""

    msg = (
        "📡 STATUS OLT MONITOR\n\n"
        f"OLT: {olt_name}\n"
        f"IP: {host}\n"
        f"SNMP: v{version}\n"
        f"{status_line}\n"
        f"{response_line}"
        f"Last check: {t_str}"
    )
    return msg.strip()
