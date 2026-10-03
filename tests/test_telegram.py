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


def test_get_main_menu_keyboard():
    from app.telegram.keyboards import get_main_menu_keyboard
    kb = get_main_menu_keyboard()
    callback_data_list = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "btn_cek_off" in callback_data_list
    assert "btn_cek_isolir" in callback_data_list
    assert "btn_cek_putus" in callback_data_list
    assert "btn_cek_redaman" in callback_data_list
    assert "btn_pelanggan_menu" in callback_data_list
    assert "btn_traffic_status" in callback_data_list


def test_handle_callback_query_edit_in_place(monkeypatch):
    from app.telegram.handlers import handle_callback_query

    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "12345")
    monkeypatch.setattr("app.telegram.handlers.get_offline_customers", lambda: [])
    monkeypatch.setattr("app.telegram.handlers.format_cek_off_report", lambda report: "Report OK")

    mock_update = MagicMock()
    mock_update.effective_chat.id = 12345
    mock_update.effective_user.id = 12345
    mock_query = MagicMock()
    mock_query.data = "btn_cek_off"
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()
    mock_update.callback_query = mock_query

    asyncio.run(handle_callback_query(mock_update, None))

    # Should edit message twice (first for loading status, second for final report)
    assert mock_query.edit_message_text.call_count == 2




