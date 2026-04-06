# 🍕 Biggus Topizza — İşletme AI Asistanı

Telegram üzerinden çalışan tam otomatik işletme finans asistanı.

## Özellikler

- 💰 Gelir / Gider / Satış takibi
- 📊 Günlük, haftalık, aylık, yıllık raporlar
- 📅 Dönem karşılaştırması (YoY, MoM)
- 📣 Reklam harcaması & satış korelasyonu
- 📄 PDF kredi kartı ekstresi otomatik analizi
- 🤖 AI destekli aylık brifing (Claude API)
- ⏰ Otomatik aylık & haftalık raporlar
- 📂 8 gider kategorisi otomatik sınıflandırma

---

## Kurulum

### 1. Repo'yu klonla

```bash
git clone https://github.com/kullanici/pizza-bot.git
cd pizza-bot
```

### 2. Sanal ortam & bağımlılıklar

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Ortam değişkenleri

```bash
cp .env.example .env
# .env dosyasını düzenle
```

**Gerekli değişkenler:**

| Değişken | Açıklama |
|----------|----------|
| `PIZZA_BOT_TOKEN` | BotFather'dan alınan token |
| `AUTHORIZED_USER_IDS` | Yetkili Telegram user ID'leri (virgülle) |
| `ADMIN_CHAT_ID` | Otomatik raporların gideceği chat ID |
| `DATABASE_URL` | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | Claude API anahtarı |

**Telegram User ID bulmak:** [@userinfobot](https://t.me/userinfobot)'a `/start` yaz.

### 4. Lokal çalıştır

```bash
python pizza_bot.py
```

---

## Railway Deploy

### 1. GitHub'a push et

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Railway'de yeni servis

1. [railway.app](https://railway.app) → New Project
2. "Deploy from GitHub repo" → repo'yu seç
3. **Mevcut projeye eklemek için:** aynı projede "New Service" → GitHub

### 3. PostgreSQL ekle

Railway Dashboard → "New" → "Database" → "PostgreSQL"

`DATABASE_URL` otomatik oluşur, servisine bağla.

### 4. Ortam değişkenlerini gir

Railway servis → "Variables" sekmesi → tüm `.env` değişkenlerini ekle.

### 5. Deploy

Railway otomatik deploy eder. Logları izle:
```
✅ Veritabanı tabloları hazır.
🍕 Biggus Topizza Bot başlatıldı!
⏰ Scheduler başlatıldı
```

---

## Komutlar

### Veri Girişi

```
/gelir 5000 yemek siparişi
/gelir 3500 online sipariş 2025-01-15    (tarihli)

/gider 800 elektrik faturası
/gider 1200 un ve peynir alımı gıda     (kategori belirt)

/satis 120 pizza 45 içecek 30 tatlı
/satis 80 pizza

/reklam 500 instagram
/reklam 300 facebook yemek kampanyası
```

### Raporlar

```
/bugun          → Bugünün özeti
/bu_hafta       → Bu haftanın özeti
/bu_ay          → Bu ayın özeti

/rapor bu_ay
/rapor gecen_ay
/rapor son_3_ay
/rapor bu_yil
/rapor 2025-01-01 2025-03-31    (özel dönem)

/karsilastir 2025-01 2024-01    (ay karşılaştırma)
/karsilastir 2025-01-01 2025-03-31 2024-01-01 2024-03-31
```

### AI Analizi

```
/ozet           → Son 30 günün AI brifing
```

PDF ekstresi gönder → Otomatik analiz & kategori tespiti

---

## Gider Kategorileri

| Kategori | Emoji | Örnekler |
|----------|-------|---------|
| gıda | 🥗 | market, hammadde, un, peynir |
| kira | 🏠 | kira, aidat |
| elektrik | ⚡ | elektrik faturası |
| su | 💧 | su faturası |
| dogalgaz | 🔥 | doğalgaz faturası |
| calisan | 👥 | maaş, SGK, personel |
| reklam | 📣 | Instagram, Facebook, Google Ads |
| diger | 📦 | diğerleri |

Bot açıklamayı okuyarak otomatik kategori tahmin eder.

---

## Otomatik Raporlar

| Zamanlama | İçerik |
|-----------|--------|
| Her ayın 1'i 08:00 | Geçen ayın tam raporu + AI brifing |
| Her Pazartesi 09:00 | Geçen haftanın özeti |

---

## Genişletme Fikirleri

- [ ] Çoklu şube desteği
- [ ] WhatsApp entegrasyonu (Twilio)
- [ ] Excel/PDF rapor export
- [ ] Stok takibi modülü
- [ ] Müşteri yorumu analizi
- [ ] Mevsimsel trend analizi
- [ ] Hedef belirleme & takip
