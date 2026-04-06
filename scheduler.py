"""
Scheduler — Otomatik Raporlar
Her ayın ilk günü bir önceki ayın raporunu gönderir.
"""

import os
import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import db
from ai_engine import aylik_brifing_olustur

logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

EMOJI_MAP = {
    "gıda": "🥗", "kira": "🏠", "elektrik": "⚡", "su": "💧",
    "dogalgaz": "🔥", "calisan": "👥", "reklam": "📣", "diger": "📦"
}

def para_formatla(tutar: float) -> str:
    return f"₺{tutar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

async def aylik_rapor_gonder(bot):
    """Her ayın 1'inde bir önceki ayın raporunu gönder"""
    if not ADMIN_CHAT_ID:
        logger.warning("ADMIN_CHAT_ID ayarlanmamış, otomatik rapor gönderilemedi.")
        return

    bugun = date.today()
    gecen_ayin_sonu = bugun.replace(day=1) - timedelta(days=1)
    gecen_ayin_baslangici = gecen_ayin_sonu.replace(day=1)

    # Önceki önceki ay (karşılaştırma için)
    onceki_bit = gecen_ayin_baslangici - timedelta(days=1)
    onceki_bas = onceki_bit.replace(day=1)

    rapor = db.donem_raporu(gecen_ayin_baslangici, gecen_ayin_sonu)
    onceki_rapor = db.donem_raporu(onceki_bas, onceki_bit)

    kar_emoji = "✅" if rapor["kar"] >= 0 else "❌"
    ay_adi = gecen_ayin_baslangici.strftime("%B %Y")

    mesaj = (
        f"📅 *AYLIK RAPOR — {ay_adi.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Toplam Gelir: *{para_formatla(rapor['toplam_gelir'])}*\n"
        f"💸 Toplam Gider: *{para_formatla(rapor['toplam_gider'])}*\n"
        f"{kar_emoji} Net Kâr: *{para_formatla(rapor['kar'])}* (%{rapor['kar_marji']:.1f})\n\n"
        f"📂 *Gider Dağılımı:*\n"
    )

    for kat, tutar in sorted(rapor["kategori_giderler"].items(), key=lambda x: x[1], reverse=True):
        emoji = EMOJI_MAP.get(kat, "📦")
        yuzde = (tutar / rapor["toplam_gider"] * 100) if rapor["toplam_gider"] > 0 else 0
        mesaj += f"  {emoji} {kat}: {para_formatla(tutar)} (%{yuzde:.0f})\n"

    # En çok satan ürünler
    if rapor["satislar"]:
        mesaj += f"\n🏆 *En Çok Satan:*\n"
        for s in rapor["satislar"][:3]:
            mesaj += f"  🍕 {s['urun']}: {s['toplam_adet']} adet\n"

    # Önceki ay karşılaştırması
    if onceki_rapor["toplam_gelir"] > 0:
        gelir_degisim = ((rapor["toplam_gelir"] - onceki_rapor["toplam_gelir"]) / onceki_rapor["toplam_gelir"]) * 100
        ok = "📈" if gelir_degisim > 0 else "📉"
        mesaj += f"\n{ok} Önceki aya göre gelir: %{gelir_degisim:+.1f}\n"

    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=mesaj,
        parse_mode="Markdown"
    )

    # AI brifing gönder
    try:
        brifing = await aylik_brifing_olustur(rapor, onceki_rapor)
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"🤖 *AI Aylık Değerlendirme*\n━━━━━━━━━━━━━━━━━━━━\n{brifing}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"AI brifing gönderilemedi: {e}")

async def haftalik_ozet_gonder(bot):
    """Her Pazartesi sabahı geçen haftanın özetini gönder"""
    if not ADMIN_CHAT_ID:
        return

    bugun = date.today()
    gecen_hafta_bit = bugun - timedelta(days=bugun.weekday() + 1)
    gecen_hafta_bas = gecen_hafta_bit - timedelta(days=6)

    rapor = db.donem_raporu(gecen_hafta_bas, gecen_hafta_bit)
    kar_emoji = "✅" if rapor["kar"] >= 0 else "❌"

    mesaj = (
        f"📊 *Haftalık Özet* ({gecen_hafta_bas.strftime('%d.%m')} — {gecen_hafta_bit.strftime('%d.%m.%Y')})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Gelir: *{para_formatla(rapor['toplam_gelir'])}*\n"
        f"💸 Gider: *{para_formatla(rapor['toplam_gider'])}*\n"
        f"{kar_emoji} Kâr: *{para_formatla(rapor['kar'])}*\n"
    )

    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=mesaj,
        parse_mode="Markdown"
    )

def setup_scheduler(app):
    """APScheduler'ı kur ve görevleri zamanla"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    scheduler = AsyncIOScheduler(timezone="Europe/Istanbul", event_loop=loop)

    # Her ayın 1'i saat 08:00'de aylık rapor
    scheduler.add_job(
        aylik_rapor_gonder,
        trigger=CronTrigger(day=1, hour=8, minute=0),
        args=[app.bot],
        id="aylik_rapor",
        name="Aylık Otomatik Rapor",
        replace_existing=True
    )

    # Her Pazartesi saat 09:00'da haftalık özet
    scheduler.add_job(
        haftalik_ozet_gonder,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        args=[app.bot],
        id="haftalik_ozet",
        name="Haftalık Özet",
        replace_existing=True
    )

    scheduler.start()
    logger.info("⏰ Scheduler başlatıldı: Aylık rapor (1. gün 08:00) + Haftalık özet (Pzt 09:00)")
    return scheduler
