"""
AI Engine — Claude API Entegrasyonu
PDF analizi + aylık brifing + reklam korelasyonu
"""

import os
import json
import base64
import logging
import anthropic
from datetime import date

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"

# ─── PDF GİDER AYRIŞTIRMA ────────────────────────────────

async def pdf_gider_ayristir(pdf_bytes: bytes, dosya_adi: str) -> dict:
    """
    Kredi kartı ekstresi PDF'ini analiz eder.
    Tüm harcamaları bulur, kategorilere ayırır.
    """
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    sistem_prompt = """Sen Biggus Topizza adlı bir pizza restoranının finans asistanısın.
Sana bir kredi kartı ekstresi PDF'i verilecek.

GÖREVIN:
1. Tüm harcama/işlemleri tespit et
2. Her işlem için şu alanları belirle:
   - tarih (YYYY-MM-DD formatında)
   - tutar (sayı, TL cinsinden)
   - aciklama (orijinal açıklama)
   - kategori (aşağıdaki listeden biri)

KATEGORİLER (kesinlikle bu listeden seç):
- gıda: market, hammadde, malzeme alımları
- kira: kira ödemeleri
- elektrik: elektrik faturaları
- su: su faturaları  
- dogalgaz: doğalgaz faturaları
- calisan: maaş, personel, SGK ödemeleri
- reklam: Instagram, Facebook, Google Ads, TikTok
- diger: diğer tüm harcamalar

ÇIKTI FORMATI — Sadece JSON döndür, başka hiçbir şey yazma:
{
  "giderler": [
    {
      "tarih": "2025-01-15",
      "tutar": 1250.00,
      "aciklama": "MIGROS 00123",
      "kategori": "gıda"
    }
  ],
  "ozet": "Kısa özet açıklaması",
  "notlar": "Dikkat çeken hususlar varsa yaz"
}"""

    response = await client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=sistem_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": f"Bu kredi kartı ekstresi PDF dosyasını ({dosya_adi}) analiz et ve tüm harcamaları JSON formatında listele."
                    }
                ]
            }
        ]
    )

    ham_yanit = response.content[0].text.strip()

    # JSON'u temizle (markdown backtick vs)
    if "```json" in ham_yanit:
        ham_yanit = ham_yanit.split("```json")[1].split("```")[0].strip()
    elif "```" in ham_yanit:
        ham_yanit = ham_yanit.split("```")[1].split("```")[0].strip()

    return json.loads(ham_yanit)


# ─── AYLIK BRİFİNG ───────────────────────────────────────

async def aylik_brifing_olustur(rapor: dict, gecen_rapor: dict) -> str:
    """
    Son 30 günün verilerini analiz ederek yönetici brifing hazırlar.
    """
    def para(x): return f"₺{x:,.2f}"

    # Karşılaştırmalı verileri hazırla
    karsilastirma = {
        "mevcut_donem": {
            "gelir": rapor["toplam_gelir"],
            "gider": rapor["toplam_gider"],
            "kar": rapor["kar"],
            "kar_marji_yuzde": rapor["kar_marji"],
            "kategori_giderler": rapor["kategori_giderler"],
            "reklam_harcamalari": rapor["reklam"],
            "en_cok_satan_urunler": [
                {"urun": s["urun"], "adet": s["toplam_adet"]}
                for s in rapor["satislar"][:5]
            ]
        },
        "onceki_donem": {
            "gelir": gecen_rapor["toplam_gelir"],
            "gider": gecen_rapor["toplam_gider"],
            "kar": gecen_rapor["kar"],
            "kar_marji_yuzde": gecen_rapor["kar_marji"],
            "kategori_giderler": gecen_rapor["kategori_giderler"],
            "reklam_harcamalari": gecen_rapor["reklam"],
        }
    }

    sistem_prompt = """Sen Biggus Topizza adlı pizza restoranının kıdemli finans danışmanısın.
Sana son 30 günün finansal verileri verilecek.

GÖREVIN:
1. Performansı önceki dönemle karşılaştır
2. Olumlu ve olumsuz trendleri tespit et
3. Reklam harcaması ile satışlar arasında korelasyon var mı değerlendir
4. Hangi kategoride aşırı harcama var?
5. Net, somut, aksiyona yönelik öneriler sun

FORMAT:
- Telegram Markdown kullan (* bold için)
- Maksimum 600 kelime
- Fazla uzun yazma, özlü ol
- Türkçe yaz
- Saat başı rapor okuyan bir işletmeci gibi pratik konuş"""

    response = await client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=sistem_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Son 30 günün ve önceki 30 günün verilerini analiz et:\n\n{json.dumps(karsilastirma, ensure_ascii=False, indent=2)}"
            }
        ]
    )

    return response.content[0].text.strip()


# ─── REKLAM KORELASYOİ ───────────────────────────────────

async def reklam_analizi_yap(reklam_verileri: list, gelir_verileri: list) -> str:
    """
    Reklam harcamaları ile gelir/satış arasındaki korelasyonu analiz eder.
    """
    sistem_prompt = """Sen bir dijital pazarlama ve finans analistinin kombinasyonusun.
Reklam harcamaları ve satış/gelir verilerini inceleyerek ROI analizi yapacaksın.

Şunlara bak:
- Reklam yapılan günlerden sonra satışlarda artış var mı?
- Hangi platform daha etkili?
- Reklam ROI'si pozitif mi negatif mi?

Türkçe, özlü, pratik önerilerle cevap ver."""

    veri = {
        "reklam_harcamalari": reklam_verileri,
        "gunluk_gelirler": gelir_verileri
    }

    response = await client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=sistem_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Bu verileri analiz et:\n{json.dumps(veri, ensure_ascii=False)}"
            }
        ]
    )

    return response.content[0].text.strip()
