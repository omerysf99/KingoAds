from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

router = Router()


async def check_member(bot: Bot, user_id: int, channel: str) -> bool:
    try:
        m = await bot.get_chat_member(channel, user_id)
        return m.status not in ("left", "kicked", "banned")
    except Exception:
        return False


def main_kb(user_id: int, admin_ids: list, admin_username: str) -> InlineKeyboardMarkup:
    rows = [
        # Reklam Ver butonu artık direkt admin DM'e yönlendiriyor
        [InlineKeyboardButton(
            text="📢 Reklam Ver",
            url=f"https://t.me/{admin_username.lstrip('@')}"
        )],
        [InlineKeyboardButton(text="📺 Kanalımı Ekle", callback_data="ch_add")],
        [InlineKeyboardButton(text="💰 Kazançlarım", callback_data="my_earnings")],
        [InlineKeyboardButton(text="👥 Referanslarım", callback_data="my_referrals")],
        [InlineKeyboardButton(text="📊 Reklamlarım", callback_data="my_ads")],
    ]
    if user_id in admin_ids:
        rows.append([InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


WELCOME = (
    "👑 <b>KingoAds</b>'e Hoş Geldiniz!\n\n"
    "💎 <b>CPM:</b> 30₺ <i>(1.000 görüntüleme başı)</i>\n"
    "🔗 <b>Referans:</b> %7 komisyon\n"
    "💳 <b>Ödeme:</b> USDT (TRC20/ERC20) • TON\n\n"
    "📢 <b>Reklam vermek için</b> aşağıdaki butona tıklayarak bize DM atın!\n\n"
    "Aşağıdan işlem seçin 👇"
)


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, db, config):
    uid = message.from_user.id
    args = message.text.split()
    ref_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_by = int(args[1][4:])
            if ref_by == uid:
                ref_by = None
        except ValueError:
            pass

    await db.upsert_user(uid, message.from_user.username, message.from_user.full_name, ref_by)

    # Zorunlu üyelik kontrolü
    if not await check_member(bot, uid, config.REQUIRED_CHANNEL):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 {config.REQUIRED_CHANNEL} Kanalına Katıl",
                                  url=f"https://t.me/{config.REQUIRED_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton(text="✅ Katıldım, Devam Et", callback_data="check_join")]
        ])
        await message.answer(
            "⛔️ Botu kullanmak için önce kanalımıza katılmalısınız!\n\n"
            f"📢 Kanal: {config.REQUIRED_CHANNEL}",
            reply_markup=kb
        )
        return

    await message.answer(WELCOME, reply_markup=main_kb(uid, config.ADMIN_IDS, config.ADMIN_USERNAME))


@router.callback_query(F.data == "check_join")
async def check_join_cb(cb: CallbackQuery, bot: Bot, config):
    if not await check_member(bot, cb.from_user.id, config.REQUIRED_CHANNEL):
        await cb.answer("❌ Henüz kanala katılmadınız!", show_alert=True)
        return
    await cb.message.edit_text(
        WELCOME,
        reply_markup=main_kb(cb.from_user.id, config.ADMIN_IDS, config.ADMIN_USERNAME)
    )
    await cb.answer("✅ Hoş geldiniz!")


@router.callback_query(F.data == "main_menu")
async def back_main(cb: CallbackQuery, config):
    await cb.message.edit_text(
        WELCOME,
        reply_markup=main_kb(cb.from_user.id, config.ADMIN_IDS, config.ADMIN_USERNAME)
    )
    await cb.answer()
