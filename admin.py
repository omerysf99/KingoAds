from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()


def is_admin(user_id: int, config) -> bool:
    return user_id in config.ADMIN_IDS


class BroadcastState(StatesGroup):
    waiting = State()


class RateState(StatesGroup):
    waiting = State()


# ─── Admin Panel Ana Menü ────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_panel")
async def admin_panel(cb: CallbackQuery, config, db):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("❌ Yetkisiz erişim.", show_alert=True)
        return
    stats = await db.get_stats()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Bekleyen Ödemeler", callback_data="admin_payments"),
         InlineKeyboardButton(text="📢 Bekleyen Reklamlar", callback_data="admin_ads")],
        [InlineKeyboardButton(text="📺 Kanal Başvuruları", callback_data="admin_channels"),
         InlineKeyboardButton(text="💸 Çekim Talepleri", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="📣 Duyuru Yap", callback_data="admin_broadcast"),
         InlineKeyboardButton(text="💱 Kur Güncelle", callback_data="admin_rates")],
        [InlineKeyboardButton(text="◀️ Ana Menü", callback_data="main_menu")],
    ])
    await cb.message.edit_text(
        f"⚙️ <b>KingoAds Admin Panel</b>\n\n"
        f"👤 Üyeler: <b>{stats['users']:,}</b>\n"
        f"📺 Kanallar: <b>{stats['channels']}</b>\n"
        f"▶️ Aktif Reklam: <b>{stats['active_ads']}</b>\n"
        f"⏳ Onay Bekleyen: <b>{stats['pending_ads']}</b>\n"
        f"💰 Toplam Gelir: <b>{stats['revenue']:.2f}₺</b>",
        reply_markup=kb
    )
    await cb.answer()


# ─── Bekleyen Ödemeler ───────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_payments")
async def admin_payments(cb: CallbackQuery, config, db):
    if not is_admin(cb.from_user.id, config):
        return
    payments = await db.get_pending_payments()
    if not payments:
        await cb.answer("✅ Bekleyen ödeme yok!", show_alert=True)
        return
    for p in payments[:5]:
        label = config.crypto_label(p["crypto_type"])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Onayla", callback_data=f"admin_pay_ok_{p['payment_id']}"),
             InlineKeyboardButton(text="❌ Reddet", callback_data=f"admin_pay_rej_{p['payment_id']}")]
        ])
        await cb.message.answer(
            f"💳 <b>Ödeme #{p['payment_id']}</b>\n\n"
            f"👤 {p['full_name']} (@{p['username']})\n"
            f"💰 {p['amount_crypto']} {label} ({p['amount_try']:.2f}₺)\n"
            f"📢 Reklam: #{p['ad_id']}\n"
            f"📅 {p['created_at'][:16]}",
            reply_markup=kb
        )
    await cb.answer()


@router.callback_query(F.data.startswith("admin_pay_ok_"))
async def confirm_payment(cb: CallbackQuery, config, db, bot: Bot):
    if not is_admin(cb.from_user.id, config):
        return
    payment_id = int(cb.data[13:])
    payment = await db.get_payment(payment_id)
    if not payment or payment["status"] != "pending":
        await cb.answer("⚠️ Zaten işleme alındı.", show_alert=True)
        return

    await db.confirm_payment(payment_id)
    await db.approve_ad(payment["ad_id"])

    # Referans komisyonu
    referrer = await db.get_referrer(payment["user_id"])
    if referrer:
        commission = payment["amount_try"] * (config.REFERRAL_PERCENT / 100)
        await db.update_balance(referrer, commission)
        await db.add_referral_earning(referrer, payment["user_id"], commission)
        try:
            await bot.send_message(
                referrer,
                f"🎉 <b>Referans Komisyonu!</b>\n\n"
                f"Davet ettiğiniz kullanıcı reklam verdi.\n"
                f"💰 Kazancınız: <b>{commission:.2f}₺</b> (%{config.REFERRAL_PERCENT})"
            )
        except Exception:
            pass

    # Reklamverende bildir
    try:
        ad = await db.get_ad(payment["ad_id"])
        await bot.send_message(
            payment["user_id"],
            f"✅ <b>Ödemeniz Onaylandı!</b>\n\n"
            f"📢 Reklamınız yayına alındı.\n"
            f"📋 Reklam No: #{payment['ad_id']}\n"
            f"👁 Hedef: {ad['target_views']:,} görüntüleme\n\n"
            "Reklamlarım bölümünden takip edebilirsiniz."
        )
    except Exception:
        pass

    await cb.message.edit_text(f"✅ Ödeme #{payment_id} onaylandı ve reklam #{payment['ad_id']} yayına alındı.")
    await cb.answer("✅ Onaylandı!")


@router.callback_query(F.data.startswith("admin_pay_rej_"))
async def reject_payment(cb: CallbackQuery, config, db, bot: Bot):
    if not is_admin(cb.from_user.id, config):
        return
    payment_id = int(cb.data[14:])
    payment = await db.get_payment(payment_id)
    if not payment:
        await cb.answer("⚠️ Bulunamadı.", show_alert=True)
        return

    await db.reject_payment(payment_id)
    await db.reject_ad(payment["ad_id"])

    try:
        await bot.send_message(
            payment["user_id"],
            f"❌ <b>Ödemeniz Reddedildi</b>\n\n"
            f"📋 Ödeme No: #{payment_id}\n\n"
            "Hatalı ödeme yaptıysanız lütfen destekle iletişime geçin."
        )
    except Exception:
        pass

    await cb.message.edit_text(f"❌ Ödeme #{payment_id} reddedildi.")
    await cb.answer("❌ Reddedildi.")


# ─── Bekleyen Reklamlar ──────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_ads")
async def admin_ads(cb: CallbackQuery, config, db):
    if not is_admin(cb.from_user.id, config):
        return
    ads = await db.get_pending_ads()
    if not ads:
        await cb.answer("✅ Bekleyen reklam yok!", show_alert=True)
        return

    for ad in ads[:5]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Onayla", callback_data=f"admin_ad_ok_{ad['ad_id']}"),
             InlineKeyboardButton(text="❌ Reddet", callback_data=f"admin_ad_rej_{ad['ad_id']}")]
        ])
        mode = "🤖 Otomatik" if ad["publish_mode"] == "auto" else f"🎯 Elle ({len(ad['selected_channels'])} kanal)"
        caption = (
            f"📢 <b>Reklam #{ad['ad_id']}</b>\n\n"
            f"👤 {ad['adv_name']} (@{ad.get('adv_username','')})\n"
            f"📂 Kategori: {ad['category']}\n"
            f"💰 Bütçe: {ad['budget_try']:.0f}₺ ({ad['target_views']:,} görüntüleme)\n"
            f"📡 Mod: {mode}\n\n"
            f"{ad['content']}"
        )
        try:
            if ad.get("photo_file_id"):
                btn_row = None
                ikb = kb
                if ad.get("button_text") and ad.get("button_url"):
                    ikb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=ad["button_text"], url=ad["button_url"])],
                        [InlineKeyboardButton(text="✅ Onayla", callback_data=f"admin_ad_ok_{ad['ad_id']}"),
                         InlineKeyboardButton(text="❌ Reddet", callback_data=f"admin_ad_rej_{ad['ad_id']}")]
                    ])
                await cb.message.answer_photo(
                    photo=ad["photo_file_id"],
                    caption=caption[:1024],
                    reply_markup=ikb
                )
            else:
                await cb.message.answer(caption, reply_markup=kb)
        except Exception as e:
            await cb.message.answer(f"Reklam #{ad['ad_id']} gösterilemedi: {e}", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("admin_ad_ok_"))
async def approve_ad(cb: CallbackQuery, config, db, bot: Bot):
    if not is_admin(cb.from_user.id, config):
        return
    ad_id = int(cb.data[12:])
    ad = await db.get_ad(ad_id)
    if not ad or ad["status"] != "pending":
        await cb.answer("⚠️ Zaten işleme alındı.", show_alert=True)
        return
    await db.approve_ad(ad_id)
    try:
        await bot.send_message(
            ad["advertiser_id"],
            f"🚀 <b>Reklamınız Onaylandı!</b>\n\n"
            f"📢 #{ad_id} nolu reklamınız yayına alındı.\n"
            f"👁 Hedef: {ad['target_views']:,} görüntüleme"
        )
    except Exception:
        pass
    await cb.message.edit_caption(caption=f"✅ Reklam #{ad_id} onaylandı.")
    await cb.answer("✅ Onaylandı!")


@router.callback_query(F.data.startswith("admin_ad_rej_"))
async def reject_ad(cb: CallbackQuery, config, db, bot: Bot):
    if not is_admin(cb.from_user.id, config):
        return
    ad_id = int(cb.data[13:])
    ad = await db.get_ad(ad_id)
    if not ad:
        await cb.answer("⚠️ Bulunamadı.", show_alert=True)
        return
    await db.reject_ad(ad_id)
    try:
        await bot.send_message(
            ad["advertiser_id"],
            f"❌ <b>Reklamınız Reddedildi</b>\n\n"
            f"📢 #{ad_id} nolu reklamınız onaylanmadı.\n"
            "Lütfen destekle iletişime geçin."
        )
    except Exception:
        pass
    await cb.answer("❌ Reddedildi.")


# ─── Kanal Başvuruları ───────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_channels")
async def admin_channels(cb: CallbackQuery, config, db):
    if not is_admin(cb.from_user.id, config):
        return
    channels = await db.get_pending_channels()
    if not channels:
        await cb.answer("✅ Bekleyen kanal başvurusu yok!", show_alert=True)
        return
    for ch in channels[:10]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Onayla", callback_data=f"admin_ch_ok_{ch['channel_id']}"),
             InlineKeyboardButton(text="❌ Reddet", callback_data=f"admin_ch_rej_{ch['channel_id']}")]
        ])
        uname = f"@{ch['username']}" if ch.get("username") else str(ch["channel_id"])
        await cb.message.answer(
            f"📺 <b>{ch['title']}</b>\n"
            f"🔗 {uname}\n"
            f"👥 {ch['member_count']:,} üye\n"
            f"📂 {ch['category']}\n"
            f"👤 Sahip: {ch['owner_name']} (@{ch.get('owner_username','')})",
            reply_markup=kb
        )
    await cb.answer()


@router.callback_query(F.data.startswith("admin_ch_ok_"))
async def approve_channel(cb: CallbackQuery, config, db, bot: Bot):
    if not is_admin(cb.from_user.id, config):
        return
    ch_id = int(cb.data[12:])
    ch = await db.get_channel(ch_id)
    if not ch:
        await cb.answer("⚠️ Bulunamadı.", show_alert=True)
        return
    await db.approve_channel(ch_id)
    try:
        await bot.send_message(
            ch["owner_id"],
            f"✅ <b>Kanalınız Onaylandı!</b>\n\n"
            f"📺 {ch['title']}\n\n"
            "Kanalınıza reklam gönderilmeye başlanacak ve görüntüleme başına kazanç elde edeceksiniz! 🎉"
        )
    except Exception:
        pass
    await cb.message.edit_text(f"✅ {ch['title']} onaylandı.")
    await cb.answer("✅ Onaylandı!")


@router.callback_query(F.data.startswith("admin_ch_rej_"))
async def reject_channel(cb: CallbackQuery, config, db, bot: Bot):
    if not is_admin(cb.from_user.id, config):
        return
    ch_id = int(cb.data[13:])
    ch = await db.get_channel(ch_id)
    if not ch:
        await cb.answer("⚠️ Bulunamadı.", show_alert=True)
        return
    await db.reject_channel(ch_id)
    try:
        await bot.send_message(
            ch["owner_id"],
            f"❌ <b>Kanal Başvurunuz Reddedildi</b>\n\n"
            f"📺 {ch['title']}\n\n"
            "Daha fazla bilgi için destekle iletişime geçin."
        )
    except Exception:
        pass
    await cb.message.edit_text(f"❌ {ch['title']} reddedildi.")
    await cb.answer("❌ Reddedildi.")


# ─── Çekim Talepleri ─────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(cb: CallbackQuery, config, db):
    if not is_admin(cb.from_user.id, config):
        return
    wds = await db.get_pending_withdrawals()
    if not wds:
        await cb.answer("✅ Bekleyen çekim yok!", show_alert=True)
        return
    for wd in wds[:10]:
        label = config.crypto_label(wd["crypto_type"])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Gönderildi", callback_data=f"admin_wd_ok_{wd['wd_id']}")]
        ])
        await cb.message.answer(
            f"💸 <b>Çekim #{wd['wd_id']}</b>\n\n"
            f"👤 {wd['full_name']} (@{wd['username']})\n"
            f"💰 {wd['amount_crypto']} {label} ({wd['amount_try']:.2f}₺)\n"
            f"📬 <code>{wd['wallet']}</code>\n"
            f"📅 {wd['created_at'][:16]}",
            reply_markup=kb
        )
    await cb.answer()


@router.callback_query(F.data.startswith("admin_wd_ok_"))
async def process_withdrawal(cb: CallbackQuery, config, db, bot: Bot):
    if not is_admin(cb.from_user.id, config):
        return
    wd_id = int(cb.data[12:])
    wds = await db.get_pending_withdrawals()
    wd = next((w for w in wds if w["wd_id"] == wd_id), None)
    if not wd:
        await cb.answer("⚠️ Zaten işleme alındı.", show_alert=True)
        return
    await db.process_withdrawal(wd_id)
    try:
        label = config.crypto_label(wd["crypto_type"])
        await bot.send_message(
            wd["user_id"],
            f"✅ <b>Ödemeniz Gönderildi!</b>\n\n"
            f"💰 {wd['amount_crypto']} {label}\n"
            f"📬 {wd['wallet']}\n\n"
            "Birkaç dakika içinde cüzdanınıza ulaşacaktır. 🎉"
        )
    except Exception:
        pass
    await cb.message.edit_text(f"✅ Çekim #{wd_id} işleme alındı.")
    await cb.answer("✅ Tamamlandı!")


# ─── Duyuru ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(cb: CallbackQuery, config, state: FSMContext):
    if not is_admin(cb.from_user.id, config):
        return
    await cb.message.edit_text(
        "📣 <b>Duyuru</b>\n\nGöndermek istediğiniz mesajı yazın\n"
        "<i>(Fotoğraf + caption da gönderebilirsiniz)</i>:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ İptal", callback_data="admin_panel")]
        ])
    )
    await state.set_state(BroadcastState.waiting)
    await cb.answer()


@router.message(BroadcastState.waiting)
async def do_broadcast(msg: Message, state: FSMContext, db, bot: Bot, config):
    if not is_admin(msg.from_user.id, config):
        return
    await state.clear()
    user_ids = await db.get_all_user_ids()
    sent = 0
    failed = 0
    status_msg = await msg.answer(f"📤 Duyuru gönderiliyor... 0/{len(user_ids)}")

    for i, uid in enumerate(user_ids):
        try:
            if msg.photo:
                await bot.send_photo(uid, msg.photo[-1].file_id, caption=msg.caption or "")
            else:
                await bot.send_message(uid, msg.text or "")
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(f"📤 Gönderiliyor... {i+1}/{len(user_ids)}")
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ <b>Duyuru Tamamlandı</b>\n\n"
        f"✉️ Gönderildi: {sent}\n"
        f"❌ Başarısız: {failed}"
    )

    # Duyuru kanalına da gönder
    try:
        if msg.photo:
            await bot.send_photo(config.ANNOUNCEMENT_CHANNEL, msg.photo[-1].file_id, caption=msg.caption or "")
        else:
            await bot.send_message(config.ANNOUNCEMENT_CHANNEL, msg.text or "")
    except Exception:
        pass


# ─── Kur Güncelle ────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_rates")
async def admin_rates(cb: CallbackQuery, config):
    if not is_admin(cb.from_user.id, config):
        return
    await cb.message.edit_text(
        f"💱 <b>Mevcut Kurlar</b>\n\n"
        f"1 USDT = {config.USDT_TO_TRY}₺\n"
        f"1 TON = {config.TON_TO_TRY}₺\n\n"
        "Yeni kur girmek için:\n"
        "<code>USDT 38.5</code> veya <code>TON 125</code> formatında yazın:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Geri", callback_data="admin_panel")]
        ])
    )
    await cb.answer()


@router.message(RateState.waiting)
async def update_rate(msg: Message, state: FSMContext, config):
    if not is_admin(msg.from_user.id, config):
        return
    parts = msg.text.strip().upper().split()
    if len(parts) != 2:
        await msg.answer("❌ Format: <code>USDT 38.5</code>")
        return
    try:
        val = float(parts[1])
        if parts[0] == "USDT":
            config.USDT_TO_TRY = val
            await msg.answer(f"✅ 1 USDT = {val}₺ olarak güncellendi.")
        elif parts[0] == "TON":
            config.TON_TO_TRY = val
            await msg.answer(f"✅ 1 TON = {val}₺ olarak güncellendi.")
        else:
            await msg.answer("❌ Geçersiz para birimi. USDT veya TON yazın.")
            return
    except ValueError:
        await msg.answer("❌ Geçersiz değer.")
    await state.clear()
