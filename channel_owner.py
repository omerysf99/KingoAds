from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

CATEGORIES = ["Genel", "Kripto", "Oyun", "Eğitim", "Teknoloji", "Eğlence", "Haber", "Spor"]


class ChFlow(StatesGroup):
    waiting_forward = State()
    select_category = State()


class WdFlow(StatesGroup):
    amount  = State()
    crypto  = State()
    wallet  = State()
    confirm = State()


# ─── Kanal Ekle ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "ch_add")
async def ch_add(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "📺 <b>Kanal Ekle</b>\n\n"
        "Kanalınızdan herhangi bir mesajı buraya <b>iletin (forward)</b>.\n\n"
        "⚠️ <b>Önce botu kanalınıza admin olarak ekleyin!</b>\n"
        "Gerekli izinler: Mesaj gönder, Mesaj düzenle",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Geri", callback_data="main_menu")]
        ])
    )
    await state.set_state(ChFlow.waiting_forward)
    await cb.answer()


@router.message(ChFlow.waiting_forward, F.forward_from_chat)
async def got_forward(msg: Message, state: FSMContext, bot: Bot, db):
    chat = msg.forward_from_chat
    if chat.type not in ("channel",):
        await msg.answer("❌ Lütfen bir <b>kanal</b> mesajı iletin.")
        return

    # Bot adminde mi?
    try:
        bot_member = await bot.get_chat_member(chat.id, (await bot.me()).id)
        if bot_member.status not in ("administrator",):
            await msg.answer(
                "❌ Bot kanalda admin değil!\n\n"
                "Lütfen botu kanalınıza admin olarak ekleyip tekrar deneyin.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Geri", callback_data="ch_add")]
                ])
            )
            return
    except Exception:
        await msg.answer("❌ Bot kanalda admin değil veya kanala erişilemiyor.")
        return

    # Üye sayısı
    try:
        count = await bot.get_chat_member_count(chat.id)
    except Exception:
        count = 0

    await state.update_data(
        channel_id=chat.id,
        channel_username=chat.username or str(chat.id),
        channel_title=chat.title,
        member_count=count
    )

    rows = []
    for i in range(0, len(CATEGORIES), 2):
        row = [InlineKeyboardButton(text=CATEGORIES[i], callback_data=f"chcat_{CATEGORIES[i]}")]
        if i + 1 < len(CATEGORIES):
            row.append(InlineKeyboardButton(text=CATEGORIES[i+1], callback_data=f"chcat_{CATEGORIES[i+1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Geri", callback_data="ch_add")])

    await msg.answer(
        f"✅ Kanal bulundu!\n\n"
        f"📺 <b>{chat.title}</b>\n"
        f"👥 Üye: {count:,}\n\n"
        "Kanal kategorisini seçin:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await state.set_state(ChFlow.select_category)


@router.message(ChFlow.waiting_forward)
async def forward_wrong(msg: Message):
    await msg.answer("❌ Lütfen kanalınızdan bir mesaj <b>iletin</b> (forward).")


@router.callback_query(ChFlow.select_category, F.data.startswith("chcat_"))
async def got_ch_category(cb: CallbackQuery, state: FSMContext, db, config, bot: Bot):
    cat = cb.data[6:]
    data = await state.get_data()

    existing = await db.get_channel(data["channel_id"])
    if existing:
        await cb.message.edit_text(
            "⚠️ Bu kanal zaten kayıtlı!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Ana Menü", callback_data="main_menu")]
            ])
        )
        await state.clear()
        await cb.answer()
        return

    await db.add_channel(
        channel_id=data["channel_id"],
        owner_id=cb.from_user.id,
        username=data["channel_username"],
        title=data["channel_title"],
        member_count=data["member_count"],
        category=cat
    )
    await state.clear()

    await cb.message.edit_text(
        f"📬 <b>Kanal Onay Bekliyor</b>\n\n"
        f"📺 {data['channel_title']}\n"
        f"📂 Kategori: {cat}\n\n"
        "Admin ekibimiz kanalınızı inceleyip onaylayacaktır.\n"
        "Onay sonrası kanalınıza reklam gönderilmeye başlanacak.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Ana Menü", callback_data="main_menu")]
        ])
    )

    # Admini bilgilendir
    ch_id = data["channel_id"]
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📺 <b>Yeni Kanal Başvurusu!</b>\n\n"
                f"📺 {data['channel_title']}\n"
                f"👥 Üye: {data['member_count']:,}\n"
                f"📂 Kategori: {cat}\n"
                f"👤 Sahip: {cb.from_user.full_name} (@{cb.from_user.username})",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Onayla", callback_data=f"admin_ch_ok_{ch_id}"),
                     InlineKeyboardButton(text="❌ Reddet", callback_data=f"admin_ch_rej_{ch_id}")]
                ])
            )
        except Exception:
            pass
    await cb.answer()


# ─── Kazançlarım ────────────────────────────────────────────────────────────
@router.callback_query(F.data == "my_earnings")
async def my_earnings(cb: CallbackQuery, db, config):
    user = await db.get_user(cb.from_user.id)
    channels = await db.get_owner_channels(cb.from_user.id)

    balance = user["balance_try"]
    total_earned = user["earned_try"]

    text = (
        f"💰 <b>Kazançlarım</b>\n\n"
        f"💵 Mevcut Bakiye: <b>{balance:.2f}₺</b>\n"
        f"📈 Toplam Kazanç: <b>{total_earned:.2f}₺</b>\n\n"
    )

    if channels:
        text += "📺 <b>Kanallarım:</b>\n"
        for ch in channels:
            ch_earn = await db.get_channel_total_earnings(ch["channel_id"])
            status = "✅" if ch["is_approved"] else "⏳"
            text += f"{status} {ch['title']} — {ch_earn:.2f}₺\n"

    rows = []
    if balance >= config.MIN_WITHDRAW:
        rows.append([InlineKeyboardButton(text="💸 Para Çek", callback_data="wd_start")])
    else:
        rows.append([InlineKeyboardButton(
            text=f"💸 Para Çek (min. {config.MIN_WITHDRAW:.0f}₺)", callback_data="wd_notenough"
        )])
    rows.append([InlineKeyboardButton(text="◀️ Geri", callback_data="main_menu")])

    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data == "wd_notenough")
async def wd_notenough(cb: CallbackQuery, config):
    await cb.answer(f"❌ Minimum çekim tutarı {config.MIN_WITHDRAW:.0f}₺!", show_alert=True)


@router.callback_query(F.data == "wd_start")
async def wd_start(cb: CallbackQuery, state: FSMContext, db, config):
    user = await db.get_user(cb.from_user.id)
    balance = user["balance_try"]
    await cb.message.edit_text(
        f"💸 <b>Para Çekme</b>\n\n"
        f"💵 Bakiyeniz: <b>{balance:.2f}₺</b>\n"
        f"📉 Minimum: {config.MIN_WITHDRAW:.0f}₺\n\n"
        "Çekmek istediğiniz tutarı girin (₺):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Geri", callback_data="my_earnings")]
        ])
    )
    await state.set_state(WdFlow.amount)
    await cb.answer()


@router.message(WdFlow.amount)
async def wd_amount(msg: Message, state: FSMContext, db, config):
    try:
        amount = float(msg.text.replace(",", ".").strip())
    except ValueError:
        await msg.answer("❌ Geçerli bir sayı girin.")
        return

    user = await db.get_user(msg.from_user.id)
    if amount < config.MIN_WITHDRAW:
        await msg.answer(f"❌ Minimum çekim: {config.MIN_WITHDRAW:.0f}₺")
        return
    if amount > user["balance_try"]:
        await msg.answer(f"❌ Yetersiz bakiye! Bakiyeniz: {user['balance_try']:.2f}₺")
        return

    await state.update_data(wd_amount=amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 TRX (Tron)", callback_data="wdcrypto_TRX")],
        [InlineKeyboardButton(text="◀️ Geri", callback_data="wd_start")],
    ])
    await msg.answer(
        f"💳 Ödeme yöntemi: <b>TRX (Tron)</b>\n\n"
        f"💰 Çekim tutarı: <b>{amount:.2f}₺</b>",
        reply_markup=kb
    )
    await state.set_state(WdFlow.crypto)


@router.callback_query(WdFlow.crypto, F.data.startswith("wdcrypto_"))
async def wd_crypto(cb: CallbackQuery, state: FSMContext, config):
    crypto = cb.data[9:]
    label = config.crypto_label(crypto)
    await state.update_data(wd_crypto=crypto)
    await cb.message.edit_text(
        f"📬 <b>{label}</b> cüzdan adresinizi girin:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Geri", callback_data="wd_start")]
        ])
    )
    await state.set_state(WdFlow.wallet)
    await cb.answer()


@router.message(WdFlow.wallet)
async def wd_wallet(msg: Message, state: FSMContext, config):
    wallet = msg.text.strip()
    data = await state.get_data()
    crypto = data["wd_crypto"]
    amount_try = data["wd_amount"]
    amount_crypto = config.try_to_crypto(amount_try, crypto)
    label = config.crypto_label(crypto)

    await state.update_data(wd_wallet=wallet, wd_amount_crypto=amount_crypto)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Onayla", callback_data="wd_confirm"),
         InlineKeyboardButton(text="❌ İptal", callback_data="my_earnings")],
    ])
    await msg.answer(
        f"📋 <b>Çekim Özeti</b>\n\n"
        f"💰 Tutar: <b>{amount_try:.2f}₺</b>\n"
        f"💎 Kripto: <b>{amount_crypto} {label}</b>\n"
        f"📬 Adres: <code>{wallet}</code>\n\n"
        "Onaylıyor musunuz?",
        reply_markup=kb
    )
    await state.set_state(WdFlow.confirm)


@router.callback_query(WdFlow.confirm, F.data == "wd_confirm")
async def wd_confirm(cb: CallbackQuery, state: FSMContext, db, config, bot: Bot):
    data = await state.get_data()
    user = await db.get_user(cb.from_user.id)

    if data["wd_amount"] > user["balance_try"]:
        await cb.answer("❌ Yetersiz bakiye!", show_alert=True)
        await state.clear()
        return

    # Bakiyeyi düş
    await db.update_balance(cb.from_user.id, -data["wd_amount"])

    wd_id = await db.create_withdrawal(
        user_id=cb.from_user.id,
        amount_try=data["wd_amount"],
        amount_crypto=data["wd_amount_crypto"],
        crypto_type=data["wd_crypto"],
        wallet=data["wd_wallet"]
    )
    await state.clear()

    label = config.crypto_label(data["wd_crypto"])

    await cb.message.edit_text(
        f"✅ <b>Çekim Talebiniz Alındı</b>\n\n"
        f"📋 Talep No: #{wd_id}\n"
        f"💰 {data['wd_amount_crypto']} {label}\n\n"
        "En kısa sürede işleme alınacaktır.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Ana Menü", callback_data="main_menu")]
        ])
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💸 <b>Yeni Çekim Talebi!</b>\n\n"
                f"📋 #{wd_id}\n"
                f"👤 {cb.from_user.full_name} (@{cb.from_user.username})\n"
                f"💰 {data['wd_amount_crypto']} {label} ({data['wd_amount']:.2f}₺)\n"
                f"📬 <code>{data['wd_wallet']}</code>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Gönderildi", callback_data=f"admin_wd_ok_{wd_id}")]
                ])
            )
        except Exception:
            pass
    await cb.answer()


# ─── Referans ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "my_referrals")
async def my_referrals(cb: CallbackQuery, db):
    stats = await db.get_referral_stats(cb.from_user.id)
    ref_link = f"https://t.me/KingoAds_Bot?start=ref_{cb.from_user.id}"
    await cb.message.edit_text(
        f"👥 <b>Referans Programı</b>\n\n"
        f"🔗 <b>Referans linkiniz:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👤 Davet ettiğiniz: <b>{stats['count']} kişi</b>\n"
        f"💰 Kazandığınız: <b>{stats['total_earned']:.2f}₺</b>\n\n"
        f"📊 Her reklamveren ödediğinde bütçenin <b>%7</b>'sini kazanırsınız!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Geri", callback_data="main_menu")]
        ])
    )
    await cb.answer()
