"""
Veritabanı — PostgreSQL şema ve yardımcı fonksiyonlar
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Tüm tabloları oluştur"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gelirler (
                id SERIAL PRIMARY KEY,
                tarih DATE NOT NULL DEFAULT CURRENT_DATE,
                tutar DECIMAL(12,2) NOT NULL,
                aciklama TEXT,
                kategori VARCHAR(100) DEFAULT 'Genel',
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS giderler (
                id SERIAL PRIMARY KEY,
                tarih DATE NOT NULL DEFAULT CURRENT_DATE,
                tutar DECIMAL(12,2) NOT NULL,
                aciklama TEXT,
                kategori VARCHAR(100) NOT NULL,
                alt_kategori VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS satislar (
                id SERIAL PRIMARY KEY,
                tarih DATE NOT NULL DEFAULT CURRENT_DATE,
                urun VARCHAR(200) NOT NULL,
                adet INTEGER NOT NULL DEFAULT 1,
                birim_fiyat DECIMAL(10,2),
                toplam DECIMAL(12,2),
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS reklam_harcamalari (
                id SERIAL PRIMARY KEY,
                tarih DATE NOT NULL DEFAULT CURRENT_DATE,
                tutar DECIMAL(12,2) NOT NULL,
                platform VARCHAR(100),
                aciklama TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS pdf_islemler (
                id SERIAL PRIMARY KEY,
                dosya_adi VARCHAR(500),
                islem_tarihi TIMESTAMP DEFAULT NOW(),
                ayristirilan_tutar DECIMAL(12,2),
                kayit_sayisi INTEGER,
                ham_metin TEXT
            );
        """)

        # İndeksler
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_gelirler_tarih ON gelirler(tarih);
            CREATE INDEX IF NOT EXISTS idx_giderler_tarih ON giderler(tarih);
            CREATE INDEX IF NOT EXISTS idx_satislar_tarih ON satislar(tarih);
            CREATE INDEX IF NOT EXISTS idx_giderler_kategori ON giderler(kategori);
        """)
    print("✅ Veritabanı tabloları hazır.")

# ─── GELİR ───────────────────────────────────────────────

def gelir_ekle(tarih: date, tutar: float, aciklama: str, kategori: str = "Genel"):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO gelirler (tarih, tutar, aciklama, kategori) VALUES (%s, %s, %s, %s) RETURNING id",
            (tarih, tutar, aciklama, kategori)
        )
        return cur.fetchone()[0]

# ─── GİDER ───────────────────────────────────────────────

GIDER_KATEGORILERI = {
    "gıda": ["gıda", "hammadde", "malzeme", "market", "sebze", "et", "un", "peynir", "domates"],
    "kira": ["kira", "aidat"],
    "elektrik": ["elektrik", "fatura"],
    "su": ["su", "su faturası"],
    "dogalgaz": ["doğalgaz", "dogalgaz", "gaz"],
    "calisan": ["maaş", "maas", "personel", "çalışan", "calisan", "sgk", "sigorta"],
    "reklam": ["reklam", "instagram", "facebook", "tiktok", "google ads", "pazarlama"],
    "diger": []
}

def kategori_tahmin(aciklama: str) -> str:
    aciklama_lower = aciklama.lower()
    for kategori, anahtar_kelimeler in GIDER_KATEGORILERI.items():
        for kelime in anahtar_kelimeler:
            if kelime in aciklama_lower:
                return kategori
    return "diger"

def gider_ekle(tarih: date, tutar: float, aciklama: str, kategori: str = None):
    if not kategori:
        kategori = kategori_tahmin(aciklama)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO giderler (tarih, tutar, aciklama, kategori) VALUES (%s, %s, %s, %s) RETURNING id",
            (tarih, tutar, aciklama, kategori)
        )
        return cur.fetchone()[0]

# ─── SATIŞ ───────────────────────────────────────────────

def satis_ekle(tarih: date, urun: str, adet: int, birim_fiyat: float = None, toplam: float = None):
    if toplam is None and birim_fiyat:
        toplam = adet * birim_fiyat
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO satislar (tarih, urun, adet, birim_fiyat, toplam) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (tarih, urun, adet, birim_fiyat, toplam)
        )
        return cur.fetchone()[0]

# ─── REKLAM ──────────────────────────────────────────────

def reklam_ekle(tarih: date, tutar: float, platform: str, aciklama: str = None):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reklam_harcamalari (tarih, tutar, platform, aciklama) VALUES (%s, %s, %s, %s) RETURNING id",
            (tarih, tutar, platform, aciklama)
        )
        # Aynı zamanda gider tablosuna da ekle
        gider_ekle(tarih, tutar, f"Reklam - {platform}", "reklam")
        return cur.fetchone()[0]

# ─── RAPORLAMA ───────────────────────────────────────────

def donem_raporu(baslangic: date, bitis: date) -> dict:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Toplam gelir
        cur.execute(
            "SELECT COALESCE(SUM(tutar), 0) as toplam FROM gelirler WHERE tarih BETWEEN %s AND %s",
            (baslangic, bitis)
        )
        toplam_gelir = float(cur.fetchone()["toplam"])

        # Toplam gider
        cur.execute(
            "SELECT COALESCE(SUM(tutar), 0) as toplam FROM giderler WHERE tarih BETWEEN %s AND %s",
            (baslangic, bitis)
        )
        toplam_gider = float(cur.fetchone()["toplam"])

        # Kategori bazlı giderler
        cur.execute("""
            SELECT kategori, COALESCE(SUM(tutar), 0) as toplam
            FROM giderler
            WHERE tarih BETWEEN %s AND %s
            GROUP BY kategori
            ORDER BY toplam DESC
        """, (baslangic, bitis))
        kategori_giderler = {row["kategori"]: float(row["toplam"]) for row in cur.fetchall()}

        # Satış özeti
        cur.execute("""
            SELECT urun, SUM(adet) as toplam_adet, COALESCE(SUM(toplam), 0) as toplam_tutar
            FROM satislar
            WHERE tarih BETWEEN %s AND %s
            GROUP BY urun
            ORDER BY toplam_adet DESC
        """, (baslangic, bitis))
        satislar = cur.fetchall()

        # Reklam harcamaları
        cur.execute("""
            SELECT platform, COALESCE(SUM(tutar), 0) as toplam
            FROM reklam_harcamalari
            WHERE tarih BETWEEN %s AND %s
            GROUP BY platform
        """, (baslangic, bitis))
        reklam = {row["platform"]: float(row["toplam"]) for row in cur.fetchall()}

        # Günlük ciro trendi
        cur.execute("""
            SELECT tarih, COALESCE(SUM(tutar), 0) as gunluk_gelir
            FROM gelirler
            WHERE tarih BETWEEN %s AND %s
            GROUP BY tarih
            ORDER BY tarih
        """, (baslangic, bitis))
        gunluk_trend = cur.fetchall()

        kar = toplam_gelir - toplam_gider
        kar_marji = (kar / toplam_gelir * 100) if toplam_gelir > 0 else 0

        return {
            "baslangic": baslangic,
            "bitis": bitis,
            "toplam_gelir": toplam_gelir,
            "toplam_gider": toplam_gider,
            "kar": kar,
            "kar_marji": kar_marji,
            "kategori_giderler": kategori_giderler,
            "satislar": [dict(s) for s in satislar],
            "reklam": reklam,
            "gunluk_trend": [dict(g) for g in gunluk_trend],
        }

def karsilastirma_raporu(donem1_baslangic: date, donem1_bitis: date,
                          donem2_baslangic: date, donem2_bitis: date) -> dict:
    donem1 = donem_raporu(donem1_baslangic, donem1_bitis)
    donem2 = donem_raporu(donem2_baslangic, donem2_bitis)

    def yuzde_degisim(yeni, eski):
        if eski == 0:
            return 100.0 if yeni > 0 else 0.0
        return ((yeni - eski) / eski) * 100

    return {
        "donem1": donem1,
        "donem2": donem2,
        "gelir_degisim": yuzde_degisim(donem1["toplam_gelir"], donem2["toplam_gelir"]),
        "gider_degisim": yuzde_degisim(donem1["toplam_gider"], donem2["toplam_gider"]),
        "kar_degisim": yuzde_degisim(donem1["kar"], donem2["kar"]),
    }
