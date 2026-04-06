"""
AI Engine — Google Gemini API Entegrasyonu
PDF analizi + aylık brifing + reklam korelasyonu
Ücretsiz tier: günde 1M token, kredi kartı gerekmez
"""

import os
import json
import base64
import logging
import google.generativeai as genai
from datetime import date

logger = logging.getLogger(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-1.5-flash"

async def pdf_gider_ayristir(pdf_bytes: bytes, dosya_adi: str) -> dict:
    model = genai.GenerativeModel(MODEL)
    prompt = """Sen Biggus Topizza adlı bir pizza restoranının finans asistanısın.
Sana bir kredi kartı ekstresi PDF'i verilecek.

GÖREVIN: Tüm harcamaları tespit et, her işlem için şu alanları belirle:
- tarih (YYYY-MM-DD), tutar (TL), aciklama, kategori

KATEGORİLER: gıda, kira, elektrik, su, dogalgaz, calisan, reklam, diger

Sadece JSON döndür, markdown kullanma:
{"giderler":[{"tarih":"2025-01-15","tutar":1250.00,"aciklama":"MIGROS","kategori":"gıda"}],"ozet":"...","notlar":"..."}"""

    pdf_part = {"mime_type": "application/pdf", "data": pdf_bytes}
    response = model.generate_content([prompt, pdf_part])
    ham_yanit = response.text.strip()
    if "```json" in ham_yanit:
        ham_yanit = ham_yanit.split("```json")[1].split("```")[0].strip()
    elif "```" in ham_yanit:
        ham_yanit = ham_yanit.split("```")[1].split("```")[0].strip()
    return json.loads(ham_yanit)

async def aylik_brifing_olustur(rapor: dict, gecen_rapor: dict) -> str:
    model = genai.GenerativeModel(
        MODEL,
        system_instruction="Sen Biggus Topizza pizza restoranının finans danışmanısın. Telegram Markdown kullan (* bold). Maks 500 kelime. Türkçe. Pratik öneriler ver."
    )
    karsilastirma = {
        "mevcut": {"gelir": rapor["toplam_gelir"], "gider": rapor["toplam_gider"], "kar": rapor["kar"], "kar_marji": rapor["kar_marji"], "kategoriler": rapor["kategori_giderler"], "reklam": rapor["reklam"], "satislar": [{"urun": s["urun"], "adet": s["toplam_adet"]} for s in rapor["satislar"][:5]]},
        "onceki": {"gelir": gecen_rapor["toplam_gelir"], "gider": gecen_rapor["toplam_gider"], "kar": gecen_rapor["kar"], "kategoriler": gecen_rapor["kategori_giderler"]}
    }
    response = model.generate_content(f"Son 30 gün vs önceki 30 gün analizi yap:\n{json.dumps(karsilastirma, ensure_ascii=False)}")
    return response.text.strip()

async def reklam_analizi_yap(reklam_verileri: list, gelir_verileri: list) -> str:
    model = genai.GenerativeModel(MODEL, system_instruction="Reklam ROI analisti. Türkçe, pratik öneriler.")
    veri = {"reklam": reklam_verileri, "gelirler": gelir_verileri}
    response = model.generate_content(f"Reklam ROI ve korelasyon analizi:\n{json.dumps(veri, ensure_ascii=False)}")
    return response.text.strip()
