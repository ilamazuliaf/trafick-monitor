"""
Unit tests for OLT Telegram Handlers (PRD Section 12.1)
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.olt.config import OLTConfig
from app.olt.handlers import (
    cek_putus_command,
    cek_redaman_command,
    olt_status_command,
)


def test_olt_handlers_unauthorized(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "12345")

    mock_update = MagicMock()
    mock_update.effective_chat.id = 99999
    mock_update.effective_user.id = 99999
    mock_update.callback_query = None
    mock_update.message.reply_text = AsyncMock()

    asyncio.run(cek_putus_command(mock_update, None))
    mock_update.message.reply_text.assert_called_once_with("⛔ Anda tidak memiliki akses ke bot ini.")


def test_olt_handlers_disabled_olt(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "12345")

    mock_update = MagicMock()
    mock_update.effective_chat.id = 12345
    mock_update.effective_user.id = 12345
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot_data = {}  # olt_monitor is None

    asyncio.run(cek_putus_command(mock_update, mock_context))
    mock_update.message.reply_text.assert_called_once_with("⚠️ Modul OLT tidak aktif.")


def test_olt_handlers_success(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "12345")

    placeholder_msg = MagicMock()
    placeholder_msg.edit_text = AsyncMock()

    mock_update = MagicMock()
    mock_update.effective_chat.id = 12345
    mock_update.effective_user.id = 12345
    mock_update.message.reply_text = AsyncMock(return_value=placeholder_msg)

    mock_monitor = AsyncMock()
    mock_monitor.config = OLTConfig(enabled=True, olt_name="OLT-UTAMA", olt_host="192.168.88.2", snmp_version="2c")
    mock_monitor.get_offline_onts.return_value = []
    mock_monitor.get_high_attenuation_onts.return_value = []
    mock_monitor.check_connection.return_value = (True, "CONNECTED", 15.5)

    mock_context = MagicMock()
    mock_context.bot_data = {"olt_monitor": mock_monitor}

    # Test /cek_putus & /olt_status
    async def _run():
        task1 = await cek_putus_command(mock_update, mock_context)
        if task1:
            await task1
        placeholder_msg.edit_text.assert_called_once()
        assert "🟢 ONT PUTUS" in placeholder_msg.edit_text.call_args[0][0]

        placeholder_msg.edit_text.reset_mock()
        task2 = await olt_status_command(mock_update, mock_context)
        if task2:
            await task2
        placeholder_msg.edit_text.assert_called_once()
        assert "🟢 CONNECTED" in placeholder_msg.edit_text.call_args[0][0]

    asyncio.run(_run())
