"""
Unit Tests for Telegram Authorization and Handlers (tambah_fitur.md Section 50)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.telegram.handlers import is_authorized, cmd_start, cmd_cek_off


def test_telegram_authorization(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "12345,67890")

    mock_update_allowed = MagicMock()
    mock_update_allowed.effective_chat.id = 12345
    mock_update_allowed.effective_user.id = 12345
    assert is_authorized(mock_update_allowed) is True

    mock_update_denied = MagicMock()
    mock_update_denied.effective_chat.id = 99999
    mock_update_denied.effective_user.id = 99999
    assert is_authorized(mock_update_denied) is False


import asyncio

def test_cmd_start_unauthorized(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "12345")

    mock_update = MagicMock()
    mock_update.effective_chat.id = 99999
    mock_update.effective_user.id = 99999
    mock_update.callback_query = None
    mock_update.message.reply_text = AsyncMock()

    asyncio.run(cmd_start(mock_update, None))
    mock_update.message.reply_text.assert_called_once_with("⛔ Anda tidak memiliki akses ke bot ini.")


