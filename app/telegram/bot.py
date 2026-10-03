"""
Telegram Bot Manager Module (tambah_fitur.md Section 28, 46, 47, 48)
Manages Telegram bot lifecycle, initialization, polling, and graceful shutdown within FastAPI event loop.
"""
from typing import Optional
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from app.core.config import settings
from app.core.logging import logger
from app.telegram import handlers


class TelegramBotRunner:
    def __init__(self):
        self.app: Optional[Application] = None
        self._is_running: bool = False

    async def start(self) -> None:
        """
        Initializes and starts polling Telegram Bot updates.
        Non-blocking execution integrated with FastAPI event loop.
        """
        if not settings.telegram_enabled:
            logger.info("Telegram Bot disabled (TELEGRAM_ENABLED=false).")
            return

        if not settings.telegram_bot_token or settings.telegram_bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            logger.warning("Telegram Bot token is not configured in .env. Skipping Telegram Bot startup.")
            return

        try:
            logger.info("Initializing Telegram Bot Application...")
            builder = Application.builder().token(settings.telegram_bot_token).concurrent_updates(True)
            self.app = builder.build()

            # Register Command Handlers
            self.app.add_handler(CommandHandler("start", handlers.cmd_start))
            self.app.add_handler(CommandHandler("menu", handlers.cmd_menu))
            self.app.add_handler(CommandHandler("pelanggan", handlers.cmd_pelanggan))
            self.app.add_handler(CommandHandler("cek_pelanggan", handlers.cmd_cek_pelanggan))
            self.app.add_handler(CommandHandler("cek_off", handlers.cmd_cek_off))
            self.app.add_handler(CommandHandler("cek_isolir", handlers.cmd_cek_isolir))

            # === OLT INTEGRATION (Conditional) ===
            if settings.olt_enabled:
                try:
                    from app.olt.config import OLTConfig
                    from app.olt.snmp.client import SNMPClient
                    from app.olt.monitor import OLTMonitor
                    from app.olt import handlers as olt_handlers

                    olt_config = OLTConfig.load()
                    snmp_client = SNMPClient(olt_config)
                    olt_monitor = OLTMonitor(olt_config, snmp_client)

                    self.app.bot_data["olt_config"] = olt_config
                    self.app.bot_data["olt_monitor"] = olt_monitor

                    self.app.add_handler(CommandHandler("cek_putus", olt_handlers.cek_putus_command))
                    self.app.add_handler(CommandHandler("cek_redaman", olt_handlers.cek_redaman_command))
                    self.app.add_handler(CommandHandler("olt_status", olt_handlers.olt_status_command))

                    logger.info(f"OLT Module aktif: {olt_config.olt_name} ({olt_config.olt_host})")
                except Exception as e:
                    logger.error(f"Gagal menginisialisasi modul OLT: {e}")
            else:
                logger.info("OLT Module tidak aktif (OLT_ENABLED=false)")


            # Register Callback Query Handler
            self.app.add_handler(CallbackQueryHandler(handlers.handle_callback_query))

            # Register Document Message Handler for Excel upload
            self.app.add_handler(MessageHandler(filters.Document.ALL, handlers.handle_document_upload))

            await self.app.initialize()
            await self.app.start()
            if self.app.updater:
                await self.app.updater.start_polling(drop_pending_updates=True)
            self._is_running = True
            logger.info("Telegram Bot started and polling active.")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}. FastAPI app will continue running.")

    async def stop(self) -> None:
        """
        Stops Telegram Bot polling and cleans up resources on application shutdown.
        """
        if self.app and self._is_running:
            logger.info("Stopping Telegram Bot...")
            try:
                if self.app.updater and self.app.updater.running:
                    await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
                logger.info("Telegram Bot stopped successfully.")
            except Exception as e:
                logger.error(f"Error stopping Telegram Bot: {e}")
            finally:
                self._is_running = False


# Global Telegram Bot Singleton Instance
telegram_bot = TelegramBotRunner()
