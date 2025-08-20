from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F
from bot.dispatcher import dp
from database.engine import engine
from sqlmodel import Session, select
from models.user import User
from models.deposit import Deposit
from services.purchase_service import PurchaseService
import math

# Note: PurchaseService needs to be instantiated in main and passed or global
purchase_service = None  # Set in main

@dp.message(CommandStart())
async def start(message: Message):
    with Session(engine) as s:
        u = s.exec(select(User).where(User.tg_id == message.from_user.id)).first()
        if not u:
            u = User(tg_id=message.from_user.id)
            s.add(u)
            s.commit()
    kb = InlineKeyboardBuilder()
    kb.button(text="Пополнить (Stars)", callback_data="deposit")
    kb.button(text="Баланс", callback_data="balance")
    await message.answer("Привет! Это бот автозакупа редких подарков/стикеров за ⭐ Stars.\nВыберите действие:", reply_markup=kb.as_markup())


@dp.callback_query(F.data == "balance")
async def balance_cb(cb: CallbackQuery):
    with Session(engine) as s:
        u = s.exec(select(User).where(User.tg_id == cb.from_user.id)).first()
        if not u:
            await cb.answer("Пользователь не найден", show_alert=True)
            return
        deposits = s.exec(select(Deposit).where(Deposit.user_id == u.id)).all()
        prov = sum(d.commission_provisional for d in deposits)
        final = sum(d.commission_final for d in deposits)
        refunded = sum(d.refunded_commission for d in deposits)
    text = (
        f"Ваш баланс: {u.stars_balance}⭐\n"
        f"Всего внесено: {u.total_contributed}⭐\n"
        f"Комиссия удержана (временная): {prov}⭐\n"
        f"Финальная комиссия по реализованным: {final}⭐\n"
        f"Возврат комиссии: {refunded}⭐"
    )
    await cb.message.edit_text(text)
    await cb.answer()


@dp.callback_query(F.data == "deposit")
async def deposit_cb(cb: CallbackQuery):
    kb = InlineKeyboardBuilder()
    for amt in (50, 133, 500, 1000):
        kb.button(text=f"+{amt}⭐", callback_data=f"sim_dep:{amt}")
    kb.button(text="Отмена", callback_data="cancel")
    await cb.message.edit_text("Выберите сумму пополнения:", reply_markup=kb.as_markup())
    await cb.answer()


@dp.callback_query(F.data.startswith("sim_dep:"))
async def sim_dep(cb: CallbackQuery):
    amt = int(cb.data.split(":", 1)[1])
    await purchase_service.apply_deposit(cb.from_user.id, amt)
    await cb.message.edit_text(f"Зачислено {amt}⭐ (симуляция). Комиссия удержана согласно конфигу.")
    await cb.answer()