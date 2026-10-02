"""
Telegram Handlers Module (tambah_fitur.md Section 11, 18, 19, 20, 21, 34-37)
Defines command, callback, and document upload handlers for Telegram Bot.
"""
from functools import wraps
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.logging import logger
from app.database.repository import CustomerRepository, backup_database
from app.services.pppoe_service import (
    get_offline_customers,
    format_cek_off_report,
    get_isolated_customers,
    format_cek_isolir_report
)
from app.telegram.keyboards import (
    get_main_menu_keyboard,
    get_customer_menu_keyboard,
    get_import_confirm_keyboard
)
from app.telegram import excel


def is_authorized(update: Update) -> bool:
    """
    Validates if user/chat is allowed to interact with the bot.
    (tambah_fitur.md Section 32 & 35)
    """
    allowed_ids = settings.telegram_allowed_chat_ids
    if not allowed_ids:
        # If no allowed IDs configured, default behavior is restrictive (Section 32)
        logger.warning("TELEGRAM_ALLOWED_CHAT_IDS is empty. Denying access.")
        return False

    chat_id = update.effective_chat.id if update.effective_chat else None
    user_id = update.effective_user.id if update.effective_user else None

    if chat_id in allowed_ids or user_id in allowed_ids:
        return True
    
    logger.warning(f"Unauthorized Telegram access attempt from chat_id: {chat_id}, user_id: {user_id}")
    return False


def auth_required(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to enforce Telegram authorization.
    (tambah_fitur.md Section 35)
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not is_authorized(update):
            msg = "⛔ Anda tidak memiliki akses ke bot ini."
            if getattr(update, "callback_query", None) is not None:
                res = update.callback_query.answer(msg, show_alert=True)
                if hasattr(res, "__await__"):
                    await res
            elif getattr(update, "message", None) is not None:
                res = update.message.reply_text(msg)
                if hasattr(res, "__await__"):
                    await res
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


@auth_required
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /start command. Displays main menu.
    """
    text = (
        "🤖 *MikroTik Traffic & PPPoE Monitor*\n\n"
        "Selamat datang! Silakan pilih menu di bawah ini:"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


@auth_required
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /menu command. Displays main menu.
    """
    text = "🤖 *Menu Utama MikroTik Monitor*"
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


@auth_required
async def cmd_pelanggan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /pelanggan command. Displays customer menu.
    """
    text = "👥 *DATA PELANGGAN PPPoE*\n\nSilakan pilih opsi manajemen pelanggan:"
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_customer_menu_keyboard()
    )


@auth_required
async def cmd_cek_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /cek_off command. Compares DB vs MikroTik active PPPoE.
    (tambah_fitur.md Section 21 & 22)
    """
    placeholder = await update.message.reply_text("⏳ Sedang memeriksa status PPPoE MikroTik...")
    try:
        report = get_offline_customers()
        formatted_text = format_cek_off_report(report)
        await placeholder.edit_text(formatted_text)
    except Exception as e:
        logger.error(f"Error executing /cek_off command: {e}")
        await placeholder.edit_text("❌ Terjadi kesalahan saat memeriksa PPPoE.")


@auth_required
async def cmd_cek_isolir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /cek_isolir command. Identifies PPPoE clients assigned IPs within ISOLATED_IP_RANGE.
    """
    placeholder = await update.message.reply_text("⏳ Sedang memeriksa pelanggan PPPoE isolir...")
    try:
        report = get_isolated_customers()
        formatted_text = format_cek_isolir_report(report)
        await placeholder.edit_text(formatted_text)
    except Exception as e:
        logger.error(f"Error executing /cek_isolir command: {e}")
        await placeholder.edit_text("❌ Terjadi kesalahan saat memeriksa pelanggan isolir.")


@auth_required
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles Inline Keyboard callback buttons.
    (tambah_fitur.md Section 20)
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "btn_main_menu":
        await query.edit_message_text(
            "🤖 *Menu Utama MikroTik Monitor*",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "btn_pelanggan_menu":
        await query.edit_message_text(
            "👥 *DATA PELANGGAN PPPoE*\n\nSilakan pilih opsi manajemen pelanggan:",
            parse_mode="Markdown",
            reply_markup=get_customer_menu_keyboard()
        )

    elif data == "btn_cek_off":
        await query.edit_message_text("⏳ Sedang memeriksa status PPPoE MikroTik...")
        report = get_offline_customers()
        formatted_text = format_cek_off_report(report)
        await query.message.reply_text(
            formatted_text,
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "btn_cek_isolir":
        await query.edit_message_text("⏳ Sedang memeriksa pelanggan PPPoE isolir...")
        report = get_isolated_customers()
        formatted_text = format_cek_isolir_report(report)
        await query.message.reply_text(
            formatted_text,
            reply_markup=get_main_menu_keyboard()
        )


    elif data == "btn_traffic_status":
        from app.database.repository import TrafficRepository
        from app.core.config import settings

        ifaces = settings.monitored_interfaces
        summary_lines = ["📊 *TRAFFIC MONITOR STATUS*\n"]
        for iface in ifaces:
            sample = TrafficRepository.get_latest_sample(iface)
            if sample:
                rx_mbps = round(sample.rx_bps / 1_000_000, 2)
                tx_mbps = round(sample.tx_bps / 1_000_000, 2)
                summary_lines.append(f"🔹 *{iface}*: RX {rx_mbps} Mbps | TX {tx_mbps} Mbps")
            else:
                summary_lines.append(f"🔹 *{iface}*: Belum ada data")

        await query.message.reply_text(
            "\n".join(summary_lines),
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "btn_dl_template":
        buffer = excel.generate_template()
        await query.message.reply_document(
            document=buffer,
            filename="template_pelanggan.xlsx",
            caption="📥 *Template Excel Pelanggan PPPoE*\n\nGunakan template ini untuk mengisi atau meng-import data pelanggan."
        )

    elif data == "btn_export_cust":
        customers = CustomerRepository.get_customers()
        if not customers:
            await query.message.reply_text("⚠️ Data pelanggan masih kosong.")
            return

        buffer = excel.export_customers(customers)
        await query.message.reply_document(
            document=buffer,
            filename="pelanggan.xlsx",
            caption="📤 *Data Pelanggan PPPoE*\n\nFile ini dapat diedit dan diupload kembali untuk memperbarui database."
        )

    elif data == "btn_import_prompt":
        await query.message.reply_text(
            "📋 *IMPORT DATA PELANGGAN*\n\n"
            "Silakan upload file Excel dengan format `.xlsx`.\n"
            "Bot akan melakukan validasi dan menampilkan preview sebelum disimpan."
        )

    elif data == "btn_confirm_import":
        pending_import = context.user_data.get("pending_import")
        if not pending_import:
            await query.edit_message_text("⚠️ Sesi import telah kedaluwarsa atau batal.")
            return

        try:
            created, updated = CustomerRepository.bulk_upsert_customers(pending_import)
            context.user_data.pop("pending_import", None)
            await query.edit_message_text(
                "✅ *IMPORT BERHASIL*\n\n"
                f"Data Baru        : {created}\n"
                f"Data Diperbarui  : {updated}\n"
                f"Total Diproses   : {created + updated}\n\n"
                "Database pelanggan telah berhasil diperbarui!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error committing customer import: {e}")
            await query.edit_message_text("❌ Gagal menyimpan data ke database. Transaction rolled back.")

    elif data == "btn_cancel_import":
        context.user_data.pop("pending_import", None)
        await query.edit_message_text("❌ Import data pelanggan dibatalkan.")


@auth_required
async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles uploaded documents (.xlsx file import validation & preview).
    (tambah_fitur.md Section 11, 16, 17, 18 & 34)
    """
    doc = update.message.document
    if not doc:
        return

    filename = doc.file_name or ""
    if not filename.lower().endswith(".xlsx"):
        await update.message.reply_text(
            "❌ Format file tidak didukung.\n\nSilakan upload file Excel:\n.xlsx"
        )
        return

    status_msg = await update.message.reply_text("⏳ Membaca dan memvalidasi file Excel...")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        result = excel.parse_and_validate_excel(bytes(file_bytes))

        if not result.get("valid", False) and "error_message" in result:
            await status_msg.edit_text(result["error_message"])
            return

        error_count = result.get("error_count", 0)
        errors = result.get("errors", [])
        total_rows = result.get("total_rows", 0)
        new_count = result.get("new_count", 0)
        update_count = result.get("update_count", 0)

        if error_count > 0:
            error_details = "\n".join([f"{idx+1}. {err}" for idx, err in enumerate(errors[:10])])
            if len(errors) > 10:
                error_details += f"\n... dan {len(errors) - 10} error lainnya."

            msg = (
                "📊 *HASIL VALIDASI EXCEL*\n\n"
                f"Total baris       : {total_rows}\n"
                f"Data baru         : {new_count}\n"
                f"Data diperbarui   : {update_count}\n"
                f"Error             : {error_count}\n\n"
                f"Error:\n{error_details}\n\n"
                "Silakan perbaiki file sebelum import."
            )
            await status_msg.edit_text(msg, parse_mode="Markdown")
            return

        # No errors -> Store in context & show preview (Section 18)
        context.user_data["pending_import"] = result["valid_customers"]

        preview_msg = (
            "📊 *DATA SIAP DIIMPORT*\n\n"
            f"Total data : {total_rows}\n"
            f"Data baru  : {new_count}\n"
            f"Update     : {update_count}\n\n"
            "Apakah ingin melanjutkan?"
        )

        await status_msg.edit_text(
            preview_msg,
            parse_mode="Markdown",
            reply_markup=get_import_confirm_keyboard()
        )

    except Exception as e:
        logger.error(f"Error processing uploaded document: {e}")
        await status_msg.edit_text("❌ Gagal memproses file Excel yang diupload.")
