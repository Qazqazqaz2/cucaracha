from aiogram.types import Message
from aiogram.filters import Command
from bot.dispatcher import dp
from utils.helpers import is_admin
from database.engine import engine
from sqlmodel import Session, select
from models.gift_type import GiftType
from models.account import Account
from models.purchase import Purchase

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    with Session(engine) as s:
        gifts = s.exec(select(GiftType)).all()
        print(gifts)
        accounts = s.exec(select(Account)).all()
        pending = s.exec(select(Purchase).where(Purchase.status == "purchased")).all()
    gifts_sorted = sorted(gifts, key=lambda g: (g.remaining_global, -g.price_stars))
    lines = ["📊 Админ-панель:"]
    if gifts_sorted:
        lines.append("\nОстатки подарков (чем меньше, тем выше приоритет):")
        for g in gifts_sorted:
            lines.append(f"• {g.title} — {g.price_stars}⭐ | осталось≈ {g.remaining_global}")
    lines.append("\nАккаунты:")
    for a in accounts[:50]:
        status = "BL" if a.blacklisted else "OK"
        lines.append(f"• {a.session_name} [{status}] кошелёк≈{a.stars_wallet}⭐ proxy={'yes' if a.proxy else 'no'}")
    lines.append(f"\nНепоставленные покупки: {len(pending)}")
    await message.answer("\n".join(lines))