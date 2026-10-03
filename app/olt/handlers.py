"""
Telegram Command Handlers for OLT Monitoring (PRD Section 8.6)
"""
import uuid
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import logger
from app.telegram.handlers import auth_required
from app.telegram.tasks import RequestContext, run_concurrent_task
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
async def cek_putus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /cek_putus command concurrently.
    (PRD Section 6.1, 6.2 & 8.6)
    """
    olt_monitor = _get_olt_monitor(context)
    if not olt_monitor or not olt_monitor.config.enabled:
        await update.message.reply_text("⚠️ Modul OLT tidak aktif.")
        return None

    request_id = str(uuid.uuid4())
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    username = update.effective_user.username if update.effective_user else None

    placeholder = await update.message.reply_text(
        f"⏳ Permintaan /cek_putus sedang diproses...\nRequest ID: {request_id[:8]}"
    )

    req_context = RequestContext(
        request_id=request_id,
        chat_id=chat_id,
        user_id=user_id,
        command="/cek_putus",
        username=username
    )

    async def _worker():
        offline_onts = await olt_monitor.get_offline_onts()
        return format_offline_onts_message(offline_onts, olt_monitor.config.olt_name)

    return run_concurrent_task(
        context=req_context,
        worker_func=_worker,
        bot=context.bot,
        message_id=getattr(placeholder, "message_id", None),
        placeholder=placeholder
    )


@restricted
async def cek_redaman_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /cek_redaman command concurrently.
    (PRD Section 6.1, 6.2 & 8.6)
    """
    olt_monitor = _get_olt_monitor(context)
    if not olt_monitor or not olt_monitor.config.enabled:
        await update.message.reply_text("⚠️ Modul OLT tidak aktif.")
        return None

    request_id = str(uuid.uuid4())
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    username = update.effective_user.username if update.effective_user else None

    placeholder = await update.message.reply_text(
        f"⏳ Permintaan /cek_redaman sedang diproses...\nRequest ID: {request_id[:8]}"
    )

    req_context = RequestContext(
        request_id=request_id,
        chat_id=chat_id,
        user_id=user_id,
        command="/cek_redaman",
        username=username
    )

    async def _worker():
        high_atten = await olt_monitor.get_high_attenuation_onts()
        return format_high_attenuation_message(
            high_atten,
            olt_monitor.config.olt_name,
            olt_monitor.config.rx_power_threshold,
        )

    return run_concurrent_task(
        context=req_context,
        worker_func=_worker,
        bot=context.bot,
        message_id=getattr(placeholder, "message_id", None),
        placeholder=placeholder
    )


@restricted
async def olt_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /olt_status command concurrently.
    (PRD Section 6.1, 6.2 & 8.6)
    """
    olt_monitor = _get_olt_monitor(context)
    if not olt_monitor or not olt_monitor.config.enabled:
        await update.message.reply_text("⚠️ Modul OLT tidak aktif.")
        return None

    request_id = str(uuid.uuid4())
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    username = update.effective_user.username if update.effective_user else None

    placeholder = await update.message.reply_text(
        f"⏳ Permintaan /olt_status sedang diproses...\nRequest ID: {request_id[:8]}"
    )

    req_context = RequestContext(
        request_id=request_id,
        chat_id=chat_id,
        user_id=user_id,
        command="/olt_status",
        username=username
    )

    async def _worker():
        connected, msg, latency = await olt_monitor.check_connection()
        formatted = format_olt_status_message(
            connected=connected,
            message=msg,
            latency_ms=latency,
            olt_name=olt_monitor.config.olt_name,
            host=olt_monitor.config.olt_host,
            version=olt_monitor.config.snmp_version,
        )
        return [formatted]

    return run_concurrent_task(
        context=req_context,
        worker_func=_worker,
        bot=context.bot,
        message_id=getattr(placeholder, "message_id", None),
        placeholder=placeholder
    )

