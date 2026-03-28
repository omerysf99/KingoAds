import os


class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    ADMIN_IDS: list = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

    # ── Reklam DM Kullanıcı Adı ───────────────────────────────────────────────
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "@kingoads_admin")

    DB_PATH: str = "kingoads.db"

    # ── Fiyatlandırma ───────────────────────────────────────────
    CPM_PRICE: float = 30.0          # Reklamveren 1000 görüntüleme için öder (₺)
    REFERRAL_PERCENT: float = 7.0    # Referans komisyonu (%)
    MIN_WITHDRAW: float = 500.0      # Minimum çekim (₺) — TRX ödeme

    # ── Kanallar ────────────────────────────────────────────────
    REQUIRED_CHANNEL: str = os.getenv("REQUIRED_CHANNEL", "@KingoAds")
    ANNOUNCEMENT_CHANNEL: str = os.getenv("ANNOUNCEMENT_CHANNEL", "@KingoAds")

    # ── Kripto Cüzdanlar ────────────────────────────────────────
    TRX_ADDRESS: str = os.getenv("TRX_ADDRESS", "TXXX_TRX_ADRESINIZ")

    # ── Döviz Kurları (manuel, otomatik güncellenebilir) ────────
    TRX_TO_TRY: float = float(os.getenv("TRX_TO_TRY", "8.5"))  # 1 TRX ≈ 8.5₺ (güncel tutun)

    # ── Görüntüleme güncelleme aralığı (saniye) ─────────────────
    VIEW_UPDATE_INTERVAL: int = 300   # 5 dakika

    def try_to_crypto(self, amount_try: float, crypto: str) -> float:
        rates = {
            "TRX": self.TRX_TO_TRY,
        }
        return round(amount_try / rates.get(crypto, self.TRX_TO_TRY), 2)

    def get_wallet(self, crypto: str) -> str:
        return {
            "TRX": self.TRX_ADDRESS,
        }.get(crypto, "")

    def crypto_label(self, crypto: str) -> str:
        return {
            "TRX": "TRX (Tron)",
        }.get(crypto, crypto)
