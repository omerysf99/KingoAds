# advertiser.py
# Reklam verme artık DM üzerinden yapıldığından bu dosyada
# sadece "Reklamlarım" (my_ads) özelliği kalmaktadır.

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


# ─── Reklamlarım ────────────────────────────────────────────────────────────
@router.callback_query(F.data == "my_ads")
async def my_ads(cb: CallbackQuery, db):
    ads = await db.get_user_ads(cb.from_user.id)
    if not ads:
        await cb.message.edit_text(
            "📊 Henüz reklamınız yok.\n\n"
            "📢 Reklam vermek için ana menüdeki <b>Reklam Ver</b> butonuna tıklayarak bize DM atın!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Geri", callback_data="main_menu")],
            ])
        )
        await cb.answer()
        return

    STATUS_EMOJI = {
        "pending": "⏳", "active": "▶️", "finished": "✅", "rejected": "❌"
    }
    text = "📊 <b>Reklamlarım</b>\n\n"
    for ad in ads[:10]:
        e = STATUS_EMOJI.get(ad["status"], "❓")
        pct = int((ad["actual_views"] / ad["target_views"] * 100)) if ad["target_views"] else 0
        text += (
            f"{e} <b>{ad['title']}</b>\n"
            f"   👁 {ad['actual_views']:,}/{ad['target_views']:,} görüntüleme ({pct}%)\n"
            f"   💰 {ad['spent_try']:.1f}₺/{ad['budget_try']:.1f}₺\n\n"
        )

    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Geri", callback_data="main_menu")]
        ])
    )
    await cb.answer()
