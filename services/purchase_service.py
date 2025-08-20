from config.settings import CFG, ADMIN_IDS
from database.engine import engine
from sqlmodel import Session, select
from services.market_service import MarketService
from services.account_service import AccountService
from database.repositories.user_repo import UserRepository
from database.repositories.deposit_repo import DepositRepository
from database.repositories.account_repo import AccountRepository
from database.repositories.gift_type_repo import GiftTypeRepository
from database.repositories.purchase_repo import PurchaseRepository
from bot.dispatcher import bot
from typing import List, Optional
from models.market_gift import MarketGift
from models.user import User
from models.account import Account
import asyncio
import math
import json

class PurchaseService:
    def __init__(self, market_service: MarketService, account_service: AccountService):
        self.market_service = market_service
        self.account_service = account_service
        self.cfg = CFG

    async def purchase_loop(self):
        while True:
            await self.account_service.scan_sessions()

            with Session(engine) as s:
                account_repo = AccountRepository(s)
                non_blacklisted_accs = account_repo.get_all_non_blacklisted()
                all_accs = account_repo.get_all()
                purchase_ids = [acc.id for acc in non_blacklisted_accs]

                # Choose scanner account: prefer non-blacklisted, otherwise fall back to any
                if non_blacklisted_accs:
                    scanner_acc = account_repo.get_by_id(non_blacklisted_accs[0].id)
                else:
                    if not all_accs:
                        print(f"No accounts in DB. Put .session files into {self.cfg.SESSIONS_DIR}")
                        await asyncio.sleep(self.cfg.SCAN_INTERVAL_SEC)
                        continue
                    scanner_acc = account_repo.get_by_id(all_accs[0].id)
                gifts_sorted = []
                try:
                    scanner_client = await self.account_service.get_client(scanner_acc)
                    gifts = await self.market_service.fetch_market(scanner_client)
                    print(gifts)
                    gift_type_repo = GiftTypeRepository(s)
                    for g in gifts:
                        gift_type_repo.create_or_update(g.code, g.title, g.price_stars, g.remaining)
                    if self.cfg.NOTIFY_ADMINS:
                        await self._notify_admins(gifts)

                    if self.cfg.PURCHASE_MODE == "limited":
                        gifts_sorted = sorted(gifts, key=lambda x: (x.remaining, -x.price_stars))
                    else:
                        gifts_sorted = sorted(gifts, key=lambda x: -x.price_stars)

                except Exception as e:
                    await self.account_service.blacklist_account(scanner_acc, f"scanner_connect_error: {e}", account_repo)
                    await asyncio.sleep(self.cfg.SCAN_INTERVAL_SEC)
                    continue

            # Perform purchases only on non-blacklisted accounts
            for acc_id in purchase_ids:
                with Session(engine) as s:
                    account_repo = AccountRepository(s)
                    acc = account_repo.get_by_id(acc_id)
                    if acc.stars_wallet >= self.cfg.MAX_STARS_PER_ACCOUNT:
                        continue

                    try:
                        client = await self.account_service.get_client(acc)
                    except Exception as e:
                        await self.account_service.blacklist_account(acc, f"connect_error: {e}", account_repo)
                        continue

                    user_repo = UserRepository(s)
                    users = user_repo.get_all()
                    users_sorted = sorted(users, key=lambda u: (-u.total_contributed, u.id))

                    gift_type_repo = GiftTypeRepository(s)
                    purchase_repo = PurchaseRepository(s)
                    deposit_repo = DepositRepository(s)

                    for g in gifts_sorted:
                        if g.remaining <= 0:
                            continue

                        price = g.price_stars
                        spendable = self.cfg.MAX_STARS_PER_ACCOUNT - acc.stars_wallet
                        if spendable < price:
                            continue

                        chosen_user: Optional[User] = None
                        for u in users_sorted:
                            if u.stars_balance >= price:
                                chosen_user = u
                                break
                        if not chosen_user:
                            continue

                        ok, meta = await self.market_service.purchase_gift(client, g.code)
                        if not ok:
                            continue

                        gt = gift_type_repo.get_by_code(g.code)
                        purchase_repo.create_purchase(gt.id, acc.id, price, chosen_user.id, meta)

                        gift_type_repo.decrement_remaining(gt)
                        acc.stars_wallet += price
                        chosen_user.stars_balance -= price

                        account_repo.update(acc)
                        user_repo.update(chosen_user)

                        deposit_repo.apply_realization_fifo(chosen_user.id, price)

                    await asyncio.sleep(self.cfg.BATCH_PURCHASE_SLEEP_MS / 1000)

            await asyncio.sleep(self.cfg.SCAN_INTERVAL_SEC)

    async def _notify_admins(self, gifts: List[MarketGift]):
        if not ADMIN_IDS:
            return
        lines = ["📢 Обновление рынка:"]
        for g in gifts:
            lines.append(f"• {g.code} | {g.title} — {g.price_stars}⭐ | остаток≈{g.remaining}")
        text = "\n".join(lines)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass

    async def delivery_loop(self):
        while True:
            with Session(engine) as s:
                purchase_repo = PurchaseRepository(s)
                pend = purchase_repo.get_pending()
                user_repo = UserRepository(s)
                account_repo = AccountRepository(s)
                for p in pend:
                    user = user_repo.get_by_id(p.owner_user_id)  # Assume added get_by_id to user_repo
                    if not user:
                        continue
                    account = account_repo.get_by_id(p.account_id)
                    if not account:
                        continue
                    try:
                        client = await self.account_service.get_client(account)
                    except Exception:
                        continue

                    sticker_id: Optional[int] = None
                    if p.ext_payload:
                        try:
                            payload = json.loads(p.ext_payload)
                            sticker_id = int(payload.get("sticker_id")) if payload.get("sticker_id") is not None else None
                        except Exception:
                            sticker_id = None
                    if sticker_id is None:
                        continue

                    ok = await self.market_service.send_gift_to_user(client, user.tg_id, sticker_id)
                    if ok:
                        purchase_repo.mark_delivered(p)
            await asyncio.sleep(2)

    async def apply_deposit(self, tg_id: int, amount: int):
        with Session(engine) as s:
            user_repo = UserRepository(s)
            u = user_repo.get_by_tg_id(tg_id)
            if not u:
                u = user_repo.create_or_update(tg_id)
            provisional = math.floor(amount * self.cfg.COMMISSION_RATE + 0.5)
            u.total_contributed += amount
            u.stars_balance += (amount - provisional)
            user_repo.update(u)
            deposit_repo = DepositRepository(s)
            deposit_repo.create_deposit(u.id, amount, self.cfg.COMMISSION_RATE)