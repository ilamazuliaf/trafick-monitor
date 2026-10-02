"""
Telegram Inline Keyboards Module (tambah_fitur.md Section 20)
Provides interactive InlineKeyboardButtons and InlineKeyboardMarkup layouts.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Returns main menu inline keyboard.
    (tambah_fitur.md Section 20)
    """
    keyboard = [
        [
            InlineKeyboardButton("🔴 Cek PPPoE OFF", callback_data="btn_cek_off"),
            InlineKeyboardButton("🟡 Cek PPPoE Isolir", callback_data="btn_cek_isolir")
        ],
        [InlineKeyboardButton("👥 Data Pelanggan", callback_data="btn_pelanggan_menu")],
        [InlineKeyboardButton("📊 Traffic Monitor", callback_data="btn_traffic_status")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_customer_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Returns customer management inline keyboard.
    (tambah_fitur.md Section 20)
    """
    keyboard = [
        [
            InlineKeyboardButton("📥 Download Template", callback_data="btn_dl_template"),
            InlineKeyboardButton("📤 Export Data Pelanggan", callback_data="btn_export_cust")
        ],
        [
            InlineKeyboardButton("📋 Import Excel", callback_data="btn_import_prompt"),
            InlineKeyboardButton("🔄 Refresh", callback_data="btn_pelanggan_menu")
        ],
        [InlineKeyboardButton("🔙 Menu Utama", callback_data="btn_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_import_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Returns confirmation inline keyboard for Excel import preview.
    (tambah_fitur.md Section 18)
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ IMPORT", callback_data="btn_confirm_import"),
            InlineKeyboardButton("❌ BATAL", callback_data="btn_cancel_import")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
