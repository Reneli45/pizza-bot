"""
Biggus Topizza — İşletme AI Asistanı
Telegram Bot — Ana Dosya
"""

import os
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from dotenv import load_dotenv
from db import init_db
from handlers import (
    gelir_handler, gider_handler, satis_handler,
    rapor_handler, karsilastir_handler, reklam_handler,
    pdf_handler, ozet_handler, start_handler, yardim_handler,
    bugun_handler, bu_hafta_handler, bu_ay_handler
)
from scheduler import setup_scheduler

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

AUTHORIZED_USERS = [int(uid) for uid in os.getenv("AUTHORIZED_USER_IDS", "").split(",") if uid]

def auth_check(func):
    """Yetkisiz erişimi engelle"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if AUTHORIZED_USERS and update.effective_user.id not in AUTHORIZED_USERS:
            await update.message.reply_text("⛔ Bu bota erişim yetkiniz yok.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper

async def post_init(application: Application):
    """Bot komutlarını ayarla"""
    commands = [
        BotCommand("start", "Botu başlat"),
        BotCommand("yardim", "Komut listesi"),
        BotCommand("gelir", "Gelir ekle: /gelir 5000 yemek siparişi"),
        BotCommand("gider", "Gider ekle: /gider 800 elektrik"),
        BotCommand("satis", "Satış ekle: /satis 120 pizza 45 icecek"),
        BotCommand("reklam", "Reklam harcaması: /reklam 500 instagram"),
        BotCommand("bugun", "Bugünün özeti"),
        BotCommand("bu_hafta", "Bu haftanın özeti"),
        BotCommand("bu_ay", "Bu ayın özeti"),
        BotCommand("rapor", "Detaylı rapor: /rapor 2025-01-01 2025-03-31"),
        BotCommand("karsilastir", "Yıllık karşılaştırma: /karsilastir 2025-01 2024-01"),
        BotCommand("ozet", "AI brifing — son 30 gün analizi"),
    ]
    await application.bot.set_my_commands(commands)

def main():
    token = os.getenv("PIZZA_BOT_TOKEN")
    if not token:
        raise ValueError("PIZZA_BOT_TOKEN env değişkeni bulunamadı!")

    init_db()

    app = Application.builder().token(token).post_init(post_init).build()

    # Komut handler'ları
    handlers = [
        ("start", start_handler),
        ("yardim", yardim_handler),
        ("gelir", gelir_handler),
        ("gider", gider_handler),
        ("satis", satis_handler),
        ("reklam", reklam_handler),
        ("bugun", bugun_handler),
        ("bu_hafta", bu_hafta_handler),
        ("bu_ay", bu_ay_handler),
        ("rapor", rapor_handler),
        ("karsilastir", karsilastir_handler),
        ("ozet", ozet_handler),
    ]

    for cmd, handler in handlers:
        app.add_handler(CommandHandler(cmd, auth_check(handler)))

    # PDF mesaj handler'ı
    app.add_handler(MessageHandler(
        filters.Document.PDF,
        auth_check(pdf_handler)
    ))

    # Scheduler (aylık otomatik rapor)
    setup_scheduler(app)

    logger.info("🍕 Biggus Topizza Bot başlatıldı!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
