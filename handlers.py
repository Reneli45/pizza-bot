"""
Telegram Komut Handler'ları — Biggus Topizza Bot
"""

import os
import re
import io
import logging
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import db
from ai_engine import (
    pdf_gider_ayristir,
    aylik_brifing_olustur,
    reklam_analizi_yap
)

logger = logging.getLogger(__name__)

EMOJI_MAP = {
    "gıda": "🥗", "kira": "🏠", "elektrik": "⚡", "su": "💧",
    "dogalgaz": "🔥", "calisan": "👥", "reklam": "📣", "diger": "📦"
}

def para_formatla(tutar: float) -> str:
    return f"₺{tutar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def yuzde_emoji(degisim: float) -> str:
    if degisim > 0:
        return f"📈 +%{degisim:.1f}"
    elif degisim < 0:
        return f"📉 %{degisim:.1f}"
    return f"➡️ %0.0"

def tarih_parse(metin: str) -> date:
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(metin, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Geçersiz tarih formatı: {metin}")

# ─── TEMEL KOMUTLAR ──────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "🍕 *Biggus Topizza AI Asistanına Hoş Geldiniz!*\n\n"
        "Ben işletmenizin akıllı finans asistanıyım.\n\n"
        "Başlamak için /yardim yazın."
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.MARKDOWN)

async def yardim_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "🍕 *Biggus Topizza Bot — Komutlar*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📥 *VERİ GİRİŞİ*\n"
        "`/gelir 5000 yemek siparişi`\n"
        "`/gelir 5000 yemek siparişi 2025-01-15`  _(tarihli)_\n\n"
        "`/gider 800 elektrik faturası`\n"
        "`/gider 1200 un ve peynir alımı gıda`  _(kategori belirt)_\n\n"
        "`/satis 120 pizza 45 içecek`\n"
        "`/satis 80 pizza`\n\n"
        "`/reklam 500 instagram`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 *RAPORLAR*\n"
        "`/bugun` — Bugünün özeti\n"
        "`/bu_hafta` — Bu haftanın özeti\n"
        "`/bu_ay` — Bu ayın özeti\n\n"
        "`/rapor 2025-01-01 2025-03-31`\n"
        "`/karsilastir 2025-01 2024-01`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 *AI ANALİZİ*\n"
        "`/ozet` — Son 30 günün AI brifing\n"
        "📎 PDF ekstresi gönderin → otomatik analiz\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📁 *GİDER KATEGORİLERİ*\n"
        "gıda · kira · elektrik · su · dogalgaz · calisan · reklam · diger"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.MARKDOWN)

# ─── VERİ GİRİŞİ ─────────────────────────────────────────

async def gelir_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /gelir 5000 yemek siparişi
    /gelir 5000 yemek siparişi 2025-01-15
    """
    args = context.args
    if not args or len(args) < 1:
        await update.message.reply_text("❌ Kullanım: `/gelir 5000 açıklama`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        tutar = float(args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Geçersiz tutar. Örnek: `/gelir 5000`", parse_mode=ParseMode.MARKDOWN)
        return

    # Son arg tarih mi?
    tarih = date.today()
    aciklama_args = args[1:]
    if aciklama_args:
        try:
            tarih = tarih_parse(aciklama_args[-1])
            aciklama_args = aciklama_args[:-1]
        except ValueError:
            pass

    aciklama = " ".join(aciklama_args) if aciklama_args else "Genel gelir"
    kayit_id = db.gelir_ekle(tarih, tutar, aciklama)

    await update.message.reply_text(
        f"✅ *Gelir kaydedildi* \\(#{kayit_id}\\)\n"
        f"💰 Tutar: *{para_formatla(tutar)}*\n"
        f"📝 Açıklama: {aciklama}\n"
        f"📅 Tarih: {tarih.strftime('%d.%m.%Y')}",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def gider_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /gider 800 elektrik faturası
    /gider 1200 un alımı gıda
    """
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("❌ Kullanım: `/gider 800 açıklama [kategori]`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        tutar = float(args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Geçersiz tutar.", parse_mode=ParseMode.MARKDOWN)
        return

    kategoriler = list(db.GIDER_KATEGORILERI.keys())
    kategori = None
    aciklama_args = args[1:]

    # Son kelime kategori mi?
    if aciklama_args and aciklama_args[-1].lower() in kategoriler:
        kategori = aciklama_args[-1].lower()
        aciklama_args = aciklama_args[:-1]

    aciklama = " ".join(aciklama_args)
    if not kategori:
        kategori = db.kategori_tahmin(aciklama)

    kayit_id = db.gider_ekle(date.today(), tutar, aciklama, kategori)
    emoji = EMOJI_MAP.get(kategori, "📦")

    await update.message.reply_text(
        f"✅ *Gider kaydedildi* \\(#{kayit_id}\\)\n"
        f"💸 Tutar: *{para_formatla(tutar)}*\n"
        f"{emoji} Kategori: {kategori}\n"
        f"📝 Açıklama: {aciklama}",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def satis_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /satis 120 pizza 45 içecek
    /satis 80 pizza
    """
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "❌ Kullanım: `/satis 120 pizza 45 içecek`\n"
            "_(adet ürün adet ürün ...)_",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Çiftler halinde parse et: adet urun adet urun ...
    satislar = []
    i = 0
    while i < len(args) - 1:
        try:
            adet = int(args[i])
            urun = args[i + 1]
            satislar.append((adet, urun))
            i += 2
        except ValueError:
            i += 1

    if not satislar:
        await update.message.reply_text("❌ Format hatası. Örnek: `/satis 120 pizza`", parse_mode=ParseMode.MARKDOWN)
        return

    mesaj_satirlari = [f"✅ *Satış kaydedildi — {date.today().strftime('%d.%m.%Y')}*\n"]
    for adet, urun in satislar:
        kayit_id = db.satis_ekle(date.today(), urun, adet)
        mesaj_satirlari.append(f"🍕 {urun}: *{adet} adet*")

    await update.message.reply_text(
        "\n".join(mesaj_satirlari),
        parse_mode=ParseMode.MARKDOWN
    )

async def reklam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reklam 500 instagram
    /reklam 300 facebook kampanya açıklaması
    """
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("❌ Kullanım: `/reklam 500 instagram [açıklama]`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        tutar = float(args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Geçersiz tutar.", parse_mode=ParseMode.MARKDOWN)
        return

    platform = args[1]
    aciklama = " ".join(args[2:]) if len(args) > 2 else None
    kayit_id = db.reklam_ekle(date.today(), tutar, platform, aciklama)

    await update.message.reply_text(
        f"✅ *Reklam harcaması kaydedildi* \\(#{kayit_id}\\)\n"
        f"📣 Platform: *{platform}*\n"
        f"💸 Tutar: *{para_formatla(tutar)}*",
        parse_mode=ParseMode.MARKDOWN_V2
    )

# ─── HIZLI RAPORLAR ──────────────────────────────────────

def rapor_mesaji_olustur(rapor: dict, baslik: str) -> str:
    kar_emoji = "✅" if rapor["kar"] >= 0 else "❌"
    kategori_satirlari = ""
    for kat, tutar in rapor["kategori_giderler"].items():
        emoji = EMOJI_MAP.get(kat, "📦")
        kategori_satirlari += f"  {emoji} {kat}: {para_formatla(tutar)}\n"

    satis_satirlari = ""
    for s in rapor["satislar"][:5]:
        satis_satirlari += f"  🍕 {s['urun']}: {s['toplam_adet']} adet\n"

    reklam_toplam = sum(rapor["reklam"].values())

    mesaj = (
        f"📊 *{baslik}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Gelir: *{para_formatla(rapor['toplam_gelir'])}*\n"
        f"💸 Gider: *{para_formatla(rapor['toplam_gider'])}*\n"
        f"{kar_emoji} Kâr: *{para_formatla(rapor['kar'])}* "
        f"(%{rapor['kar_marji']:.1f} kâr marjı)\n\n"
    )

    if kategori_satirlari:
        mesaj += f"📂 *Gider Kategorileri:*\n{kategori_satirlari}\n"

    if satis_satirlari:
        mesaj += f"🛒 *En Çok Satan Ürünler:*\n{satis_satirlari}\n"

    if reklam_toplam > 0:
        mesaj += f"📣 Reklam Harcaması: {para_formatla(reklam_toplam)}\n"

    return mesaj

async def bugun_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bugun = date.today()
    rapor = db.donem_raporu(bugun, bugun)
    mesaj = rapor_mesaji_olustur(rapor, f"Bugünün Özeti — {bugun.strftime('%d.%m.%Y')}")
    await update.message.reply_text(mesaj, parse_mode=ParseMode.MARKDOWN)

async def bu_hafta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bugun = date.today()
    haftanin_baslangici = bugun - timedelta(days=bugun.weekday())
    rapor = db.donem_raporu(haftanin_baslangici, bugun)
    mesaj = rapor_mesaji_olustur(
        rapor,
        f"Bu Hafta — {haftanin_baslangici.strftime('%d.%m')} / {bugun.strftime('%d.%m.%Y')}"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.MARKDOWN)

async def bu_ay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bugun = date.today()
    ayin_baslangici = bugun.replace(day=1)
    rapor = db.donem_raporu(ayin_baslangici, bugun)
    mesaj = rapor_mesaji_olustur(
        rapor,
        f"Bu Ay — {ayin_baslangici.strftime('%B %Y')}"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.MARKDOWN)

# ─── DETAYLI RAPOR ───────────────────────────────────────

async def rapor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /rapor 2025-01-01 2025-03-31
    /rapor bu_ay
    /rapor gecen_ay
    """
    args = context.args
    bugun = date.today()

    if not args:
        await update.message.reply_text(
            "❌ Kullanım:\n"
            "`/rapor 2025-01-01 2025-03-31`\n"
            "`/rapor bu_ay`\n"
            "`/rapor gecen_ay`\n"
            "`/rapor son_3_ay`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        if args[0] == "bu_ay":
            bas = bugun.replace(day=1)
            bit = bugun
        elif args[0] == "gecen_ay":
            gecen = bugun - relativedelta(months=1)
            bas = gecen.replace(day=1)
            bit = (bugun.replace(day=1) - timedelta(days=1))
        elif args[0] == "son_3_ay":
            bas = (bugun - relativedelta(months=3)).replace(day=1)
            bit = bugun
        elif args[0] == "bu_yil":
            bas = bugun.replace(month=1, day=1)
            bit = bugun
        elif len(args) >= 2:
            bas = tarih_parse(args[0])
            bit = tarih_parse(args[1])
        else:
            raise ValueError("Geçersiz argüman")

        rapor = db.donem_raporu(bas, bit)
        gun_sayisi = (bit - bas).days + 1
        gunluk_ort = rapor["toplam_gelir"] / gun_sayisi if gun_sayisi > 0 else 0

        mesaj = rapor_mesaji_olustur(
            rapor,
            f"Rapor: {bas.strftime('%d.%m.%Y')} — {bit.strftime('%d.%m.%Y')}"
        )
        mesaj += f"\n📅 Dönem: {gun_sayisi} gün | Günlük Ort: {para_formatla(gunluk_ort)}"

        await update.message.reply_text(mesaj, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")

# ─── KARŞILAŞTIRMA ───────────────────────────────────────

async def karsilastir_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /karsilastir 2025-01 2024-01   (ay karşılaştırma)
    /karsilastir 2025-01-01 2025-01-31 2024-01-01 2024-01-31  (özel dönem)
    """
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "❌ Kullanım:\n"
            "`/karsilastir 2025-01 2024-01`\n"
            "`/karsilastir 2025-01-01 2025-03-31 2024-01-01 2024-03-31`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        if len(args) == 2 and len(args[0]) == 7:
            # Ay formatı: YYYY-MM
            def ay_aralik(ay_str):
                yil, ay = map(int, ay_str.split("-"))
                bas = date(yil, ay, 1)
                bit = (bas + relativedelta(months=1)) - timedelta(days=1)
                return bas, bit

            d1_bas, d1_bit = ay_aralik(args[0])
            d2_bas, d2_bit = ay_aralik(args[1])
        elif len(args) == 4:
            d1_bas = tarih_parse(args[0])
            d1_bit = tarih_parse(args[1])
            d2_bas = tarih_parse(args[2])
            d2_bit = tarih_parse(args[3])
        else:
            raise ValueError("Geçersiz format")

        k = db.karsilastirma_raporu(d1_bas, d1_bit, d2_bas, d2_bit)
        d1 = k["donem1"]
        d2 = k["donem2"]

        mesaj = (
            f"📊 *Dönem Karşılaştırması*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Dönem 1:* {d1_bas.strftime('%d.%m.%Y')} — {d1_bit.strftime('%d.%m.%Y')}\n"
            f"*Dönem 2:* {d2_bas.strftime('%d.%m.%Y')} — {d2_bit.strftime('%d.%m.%Y')}\n\n"
            f"💰 Gelir:\n"
            f"  D1: {para_formatla(d1['toplam_gelir'])} | D2: {para_formatla(d2['toplam_gelir'])}\n"
            f"  {yuzde_emoji(k['gelir_degisim'])}\n\n"
            f"💸 Gider:\n"
            f"  D1: {para_formatla(d1['toplam_gider'])} | D2: {para_formatla(d2['toplam_gider'])}\n"
            f"  {yuzde_emoji(k['gider_degisim'])}\n\n"
            f"✅ Kâr:\n"
            f"  D1: {para_formatla(d1['kar'])} | D2: {para_formatla(d2['kar'])}\n"
            f"  {yuzde_emoji(k['kar_degisim'])}\n"
        )

        # Kategori bazlı gider karşılaştırması
        tum_kategoriler = set(list(d1["kategori_giderler"].keys()) + list(d2["kategori_giderler"].keys()))
        if tum_kategoriler:
            mesaj += "\n📂 *Gider Kategori Karşılaştırması:*\n"
            for kat in sorted(tum_kategoriler):
                t1 = d1["kategori_giderler"].get(kat, 0)
                t2 = d2["kategori_giderler"].get(kat, 0)
                degisim = ((t1 - t2) / t2 * 100) if t2 > 0 else 100.0
                emoji = EMOJI_MAP.get(kat, "📦")
                ok = "🔴" if degisim > 10 else ("🟢" if degisim < -10 else "🟡")
                mesaj += f"  {emoji} {kat}: {para_formatla(t1)} {ok} {yuzde_emoji(degisim)}\n"

        await update.message.reply_text(mesaj, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")

# ─── AI ÖZETİ ────────────────────────────────────────────

async def ozet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Son 30 günün AI brifing"""
    await update.message.reply_text("🤖 AI analizi hazırlanıyor, lütfen bekleyin...")

    bugun = date.today()
    bas = bugun - timedelta(days=29)
    rapor = db.donem_raporu(bas, bugun)

    gecen_bas = bas - timedelta(days=30)
    gecen_bit = bas - timedelta(days=1)
    gecen_rapor = db.donem_raporu(gecen_bas, gecen_bit)

    try:
        brifing = await aylik_brifing_olustur(rapor, gecen_rapor)
        await update.message.reply_text(
            f"🤖 *AI Brifing — Son 30 Gün*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{brifing}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"AI brifing hatası: {e}")
        await update.message.reply_text("❌ AI analizi şu an kullanılamıyor. Temel rapor için /rapor son_30_gun deneyin.")

# ─── PDF HANDLER ─────────────────────────────────────────

async def pdf_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kredi kartı ekstresi PDF'ini analiz et"""
    doc = update.message.document

    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("❌ Lütfen PDF formatında bir dosya gönderin.")
        return

    await update.message.reply_text(
        f"📄 *{doc.file_name}* alındı.\n"
        f"🤖 AI analiz ediyor, lütfen bekleyin...",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        # Dosyayı indir
        file = await context.bot.get_file(doc.file_id)
        pdf_bytes = await file.download_as_bytearray()

        # AI ile analiz et
        sonuc = await pdf_gider_ayristir(bytes(pdf_bytes), doc.file_name)

        # Bulunan giderleri kaydet
        kaydedilen = 0
        for gider in sonuc.get("giderler", []):
            try:
                db.gider_ekle(
                    tarih=date.fromisoformat(gider.get("tarih", str(date.today()))),
                    tutar=float(gider["tutar"]),
                    aciklama=gider.get("aciklama", "PDF'den aktarıldı"),
                    kategori=gider.get("kategori", "diger")
                )
                kaydedilen += 1
            except Exception as ge:
                logger.warning(f"Gider kayıt hatası: {ge}")

        # Özet mesaj
        toplam_tutar = sum(float(g["tutar"]) for g in sonuc.get("giderler", []))
        mesaj = (
            f"✅ *PDF Analizi Tamamlandı*\n\n"
            f"📊 Bulunan işlem: {len(sonuc.get('giderler', []))}\n"
            f"✅ Kaydedilen: {kaydedilen}\n"
            f"💸 Toplam: {para_formatla(toplam_tutar)}\n\n"
            f"📂 *Kategori Özeti:*\n"
        )

        # Kategori dağılımı
        kat_toplam = {}
        for g in sonuc.get("giderler", []):
            kat = g.get("kategori", "diger")
            kat_toplam[kat] = kat_toplam.get(kat, 0) + float(g["tutar"])

        for kat, tutar in sorted(kat_toplam.items(), key=lambda x: x[1], reverse=True):
            emoji = EMOJI_MAP.get(kat, "📦")
            mesaj += f"  {emoji} {kat}: {para_formatla(tutar)}\n"

        if sonuc.get("notlar"):
            mesaj += f"\n💡 *AI Notu:* {sonuc['notlar']}"

        await update.message.reply_text(mesaj, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"PDF işleme hatası: {e}")
        await update.message.reply_text(
            f"❌ PDF işlenirken hata oluştu: {str(e)}\n"
            f"Lütfen okunabilir (taranmamış) bir PDF gönderin."
        )
