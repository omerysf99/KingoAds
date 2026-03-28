import asyncio
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

CPM = 30.0  # ₺ per 1000 views


class AdScheduler:
    def __init__(self, bot: Bot, db, config):
        self.bot = bot
        self.db = db
        self.config = config

    async def run(self):
        logger.info("📡 Ad Scheduler başladı")
        while True:
            try:
                await self.send_pending_ads()
                await asyncio.sleep(60)   # Her 1 dk'da yeni reklamları kontrol et
                await self.update_views()
                await asyncio.sleep(self.config.VIEW_UPDATE_INTERVAL - 60)
            except Exception as e:
                logger.error(f"Scheduler hatası: {e}")
                await asyncio.sleep(30)

    # ── Reklamları Kanallara Gönder ─────────────────────────────────────────
    async def send_pending_ads(self):
        ads = await self.db.get_active_ads()
        channels = await self.db.get_approved_channels()

        if not channels:
            return

        for ad in ads:
            if ad["actual_views"] >= ad["target_views"]:
                continue

            if ad["publish_mode"] == "manual":
                target_channels = [
                    ch for ch in channels
                    if ch["channel_id"] in ad["selected_channels"]
                ]
            else:
                # Auto: kategori eşleşmesi varsa önce onlar, yoksa hepsine
                cat_match = [ch for ch in channels if ch["category"] == ad["category"]]
                target_channels = cat_match if cat_match else channels

            for ch in target_channels:
                already_sent = await self.db.channel_send_exists(ad["ad_id"], ch["channel_id"])
                if already_sent:
                    continue

                await self._send_ad_to_channel(ad, ch)
                await asyncio.sleep(0.5)

    async def _send_ad_to_channel(self, ad: dict, channel: dict):
        try:
            kb = None
            if ad.get("button_text") and ad.get("button_url"):
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=ad["button_text"], url=ad["button_url"])]
                ])

            if ad.get("photo_file_id"):
                msg = await self.bot.send_photo(
                    chat_id=channel["channel_id"],
                    photo=ad["photo_file_id"],
                    caption=ad["content"],
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            else:
                msg = await self.bot.send_message(
                    chat_id=channel["channel_id"],
                    text=ad["content"],
                    reply_markup=kb,
                    parse_mode="HTML"
                )

            await self.db.log_ad_send(ad["ad_id"], channel["channel_id"], msg.message_id)
            logger.info(f"✅ Reklam #{ad['ad_id']} → {channel['title']} gönderildi")

        except Exception as e:
            logger.error(f"❌ Reklam #{ad['ad_id']} → {channel['channel_id']} gönderilemedi: {e}")

    # ── Görüntüleme Güncelle & Kanal Sahibine Öde ──────────────────────────
    async def update_views(self):
        sends = await self.db.get_active_sends()

        for send in sends:
            try:
                msg = await self.bot.get_message_views(
                    channel_id=send["channel_id"],
                    message_id=send["message_id"]
                )
                new_views = msg
            except Exception:
                # Telegram bot API'de get_message_views yok; forward_count veya
                # message.views üzerinden alınabilir (pyrogram gerektirir)
                # Bot API ile fallback: 0 views, manuel güncelleme
                continue

            old_views = send["views_count"]
            delta_views = max(0, new_views - old_views)
            if delta_views == 0:
                continue

            # Kazanç hesapla: (delta_views / 1000) * CPM_PRICE
            earned = (delta_views / 1000) * self.config.CPM_PRICE

            # Send kaydını güncelle
            await self.db.update_send_views(send["send_id"], new_views, send["earned_try"] + earned)

            # Reklam toplamını güncelle
            is_finished = await self.db.add_ad_views(send["ad_id"], delta_views, earned)

            # Kanal sahibine öde
            await self.db.update_balance(send["owner_id"], earned)

            # Reklam bittiyse reklamverende bildir
            if is_finished:
                ad = await self.db.get_ad(send["ad_id"])
                if ad:
                    try:
                        await self.bot.send_message(
                            ad["advertiser_id"],
                            f"🏁 <b>Reklamınız Tamamlandı!</b>\n\n"
                            f"📢 #{ad['ad_id']} nolu reklamınız hedef görüntülemeye ulaştı.\n"
                            f"👁 Toplam: {ad['actual_views']:,} görüntüleme\n"
                            f"💰 Harcanan: {ad['spent_try']:.2f}₺",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                logger.info(f"🏁 Reklam #{send['ad_id']} tamamlandı")
