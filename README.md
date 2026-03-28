# 👑 KingoAds — @KingoAds_Bot

Kripto ödemeli (USDT/TON) Telegram fotoğraflı reklam yayın sistemi.

## Özellikler

- 📸 **Fotoğraflı reklam** (caption + opsiyonel buton)
- 💳 **Kripto ödeme**: USDT TRC20, USDT ERC20, TON
- 💰 **CPM sistemi**: 30₺ per 1.000 görüntüleme
- 🎯 **Kanal seçimi**: Otomatik dağıtım VEYA elle kanal seçimi
- 👥 **Referans**: %7 komisyon
- 📺 **Kanal sahipleri**: Görüntüleme başına otomatik kazanç
- 💸 **Para çekme**: Kripto ile çekim talebi
- 📣 **Duyuru sistemi**: Tüm kullanıcılara + kanala
- ⚙️ **Admin panel**: Bot üzerinden inline butonlar

---

## Kurulum

### 1. Gereksinimler
```bash
Python 3.10+
```

### 2. Bağımlılıkları Yükle
```bash
pip install -r requirements.txt
```

### 3. .env Dosyası
```bash
cp .env.example .env
nano .env   # kendi değerlerinizi girin
```

### 4. BotFather Ayarları
[@BotFather](https://t.me/BotFather) üzerinde:
```
/newbot → KingoAds → @KingoAds_Bot
/setname → KingoAds
/setdescription → Kripto ödemeli Telegram reklam platformu
/setuserpic → Logo yükle
```

### 5. Botu Çalıştır
```bash
python bot.py
```

---

## Dosya Yapısı

```
kingoads/
├── bot.py              # Ana giriş noktası
├── config.py           # Konfigürasyon
├── database.py         # SQLite veritabanı
├── requirements.txt
├── .env.example
├── handlers/
│   ├── common.py       # /start, üyelik kontrolü
│   ├── advertiser.py   # Reklam oluşturma & ödeme
│   ├── channel_owner.py # Kanal ekleme, kazanç, çekim
│   └── admin.py        # Admin paneli
└── services/
    └── scheduler.py    # Reklam gönderimi & görüntüleme takibi
```

---

## Akış

### Reklamveren
1. `/start` → Ana menü
2. **Reklam Ver** → Başlık → Metin → Fotoğraf → (Buton?) → Kategori
3. **Yayın Modu**: Otomatik VEYA Elle Kanal Seç
4. Bütçe gir (30₺ = 1.000 görüntüleme)
5. Kripto seç → Ödeme adresine gönder → "Ödemeyi Yaptım"
6. Admin onaylar → Reklam yayına girer

### Kanal Sahibi
1. Botu kanala admin olarak ekle
2. **Kanalımı Ekle** → Kanaldan mesaj ilet → Kategori seç
3. Admin onaylar
4. Reklamlar otomatik gönderilir, görüntüleme başına kazanç
5. **Kazançlarım** → **Para Çek** → Kripto + Cüzdan → Admin öder

### Admin
- **Admin Panel** → Ödemeler / Reklamlar / Kanallar / Çekimler / Duyuru / Kur

---

## Görüntüleme Takibi Notu

Telegram Bot API'si `get_message_views` desteklemiyor.  
Görüntüleme sayısı için 2 seçenek:

**Seçenek A — Pyrogram (önerilen)**
```bash
pip install pyrogram tgcrypto
```
`scheduler.py`'de `get_message_views` kısmını Pyrogram ile doldurun.

**Seçenek B — Manuel/Webhook**
Admin panelinden elle görüntüleme güncellemesi yapılabilir.

---

## Lisans
MIT
