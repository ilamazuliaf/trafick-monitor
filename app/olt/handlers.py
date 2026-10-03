"""
Telegram Command Handlers for OLT Monitoring (PRD Section 8.6)
"""
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import logger
from app.telegram.handlers import auth_required
from app.olt.monitor import OLTMonitor
from app.olt.messages import (
    format_offline_onts_message,
    format_high_attenuation_message,
    format_olt_status_message,
)

# Alias decorator as specified in PRD Section 8.6
restricted = auth_required


def _get_olt_monitor(context: ContextTypes.DEFAULT_TYPE) -> Optional[OLTMonitor]:
    if context and context.bot_data:
        return context.bot_data.get("olt_monitor")
    return None


@restricted
async def cek_putus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /cek_putus command.
    (PRD Section 6.1, 6.2 & 8.6)
    """
    olt_monitor = _get_olt_monitor(context)
    if not olt_monitor or not olt_monitor.config.enabled:
        await update.message.reply_text("⚠️ Modul OLT tidak aktif.")
        return

    placeholder = await update.message.reply_text("⏳ Sedang memeriksa ONT putus...")
    try:
        offline_onts = await olt_monitor.get_offline_onts()
        msg_list = format_offline_onts_message(offline_onts, olt_monitor.config.olt_name)

        if msg_list:
            await placeholder.edit_text(msg_list[0])
            for m in msg_list[1:]:
                await update.message.reply_text(m)
    except Exception as e:
        logger.error(f"Error executing /cek_putus: {e}", exc_info=True)
        await placeholder.edit_text("❌ Terjadi kesalahan saat memeriksa status ONT.")


@restricted
async def cek_redaman_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /cek_redaman command.
    (PRD Section 6.1, 6.2 & 8.6)
    """
    olt_monitor = _get_olt_monitor(context)
    if not olt_monitor or not olt_monitor.config.enabled:
        await update.message.reply_text("⚠️ Modul OLT tidak aktif.")
        return

    placeholder = await update.message.reply_text("⏳ Sedang memeriksa redaman ONT...")
    try:
        high_atten = await olt_monitor.get_high_attenuation_onts()
        msg_list = format_high_attenuation_message(
            high_atten,
            olt_monitor.config.olt_name,
            olt_monitor.config.rx_power_threshold,
        )

        if msg_list:
            await placeholder.edit_text(msg_list[0])
            for m in msg_list[1:]:
                await update.message.reply_text(m)
    except Exception as e:
        logger.error(f"Error executing /cek_redaman: {e}", exc_info=True)
        await placeholder.edit_text("❌ Terjadi kesalahan saat memeriksa redaman ONT.")


@restricted
async def olt_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /olt_status command.
    (PRD Section 6.1, 6.2 & 8.6)
    """
    olt_monitor = _get_olt_monitor(context)
    if not olt_monitor or not olt_monitor.config.enabled:
        await update.message.reply_text("⚠️ Modul OLT tidak aktif.")
        return

    placeholder = await update.message.reply_text("⏳ Sedang memeriksa status koneksi OLT...")
    try:
        connected, msg, latency = await olt_monitor.check_connection()
        formatted = format_olt_status_message(
            connected=connected,
            message=msg,
            latency_ms=latency,
            olt_name=olt_monitor.config.olt_name,
            host=olt_monitor.config.olt_host,
            version=olt_monitor.config.snmp_version,
        )
        await placeholder.edit_text(formatted)
    except Exception as e:
        logger.error(f"Error executing /olt_status: {e}", exc_info=True)
        await placeholder.edit_text("❌ Terjadi kesalahan saat memeriksa status OLT.")
