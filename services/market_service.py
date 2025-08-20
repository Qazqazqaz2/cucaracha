from telethon import TelegramClient
from typing import List, Tuple, Optional
from models.market_gift import MarketGift
from telethon.tl import functions as tl_functions, types as tl_types
from telethon.extensions import BinaryReader
from telethon.errors import RPCError
from utils.tl_utils import _TLWriter, _RawGetStarGifts

class MarketService:

    async def fetch_market(self, client: TelegramClient) -> List[MarketGift]:
        """
        Реализовано вручную по TL-схеме Stars Gifts: payments.getStarGifts
        Docs: https://core.telegram.org/api/stars
        """
        # Попытаемся вызвать нативный метод, если Telethon его поддерживает
        try:
            options = await client(tl_functions.payments.GetStarGiftsRequest(hash=0))
            parsed = []
            for opt in options.gifts:
                remaining = getattr(opt, "availability_remains", 999999) if getattr(opt, "limited", False) else 999999
                if getattr(opt, "sold_out", False):
                    remaining = 0
                parsed.append({
                    "id": getattr(opt, "id", 0),
                    "stars": int(getattr(opt, "stars", 0)),
                    "remaining": remaining,
                    "sold_out": getattr(opt, "sold_out", False),
                })
        except Exception as e:
            print("[MarketClient] native getStarGifts failed:", e)
            # Ручной запрос через TL-конструктор
            try:
                raw_req = _RawGetStarGifts()
                parsed = await client(raw_req)
            except Exception as e:
                print("[MarketClient] manual getStarGifts failed:", e)
                return []

        gifts: List[MarketGift] = []
        for item in parsed:
            try:
                id_ = item.get("id", 0)
                stars_amount = int(item.get("stars", 0))
                remaining = int(item.get("remaining", 999999))
                if item.get("sold_out", False):
                    remaining = 0
                gifts.append(
                    MarketGift(
                        code=str(id_),
                        title=f"Star Gift {stars_amount}",
                        price_stars=stars_amount,
                        remaining=remaining,
                    )
                )
            except Exception:
                continue
        return gifts

    async def purchase_gift(self, client: TelegramClient, gift_code: str) -> Tuple[bool, dict]:
        """
        Покупка Stars-подарка требует платёжного флоу (inputInvoiceStars + payments.sendStarsForm).
        Не реализовано в рамках этого проекта.
        """
        return False, {"error": "Stars gift purchase requires payments flow (not implemented)"}

    async def send_gift_to_user(self, client: TelegramClient, user_id: int, sticker_id: int) -> bool:
        # Отправка Stars-подарка — платёжный флоу; не реализовано здесь.
        return False

    async def get_stars_status(self, client: TelegramClient):
        """
        payments.getStarsStatus для текущего аккаунта.
        Docs: https://core.telegram.org/type/payments.StarsStatus
        """
        try:
            return await client(tl_functions.payments.GetStarsStatus(peer=tl_types.InputPeerSelf()))
        except Exception as e:
            print("[MarketClient] getStarsStatus error:", e)
            return None

    async def convert_star_gift(self, client: TelegramClient, sender_user_id: int, msg_id: int) -> bool:
        """
        payments.convertStarGift — конвертировать полученный Gift в Stars.
        Docs: https://core.telegram.org/method/payments.convertStarGift
        """
        try:
            user = await client.get_entity(sender_user_id)
            input_user = await client.get_input_entity(user)
            ok = await client(tl_functions.payments.ConvertStarGift(user_id=input_user, msg_id=msg_id))
            return bool(ok)
        except Exception as e:
            print("[MarketClient] convertStarGift error:", e)
            return False


if __name__ == "__main__":
    import asyncio
    import argparse
    import datetime

    from sqlmodel import Session
    from database.engine import engine
    from database.repositories.account_repo import AccountRepository

    # Import inside CLI to avoid circular imports during normal usage
    from services.account_service import AccountService

    async def scan_gifts_once(include_blacklisted: bool = False, preferred_session: str | None = None):
        account_service = AccountService()
        market_service = MarketService()

        # Ensure we have at least one account available
        await account_service.scan_sessions()
        with Session(engine) as s:
            repo = AccountRepository(s)
            all_accounts = repo.get_all()
            non_blacklisted = [a for a in all_accounts if not a.blacklisted]

            # Diagnostics
            if not non_blacklisted:
                sessions_dir = __import__("config.settings", fromlist=["CFG"]).CFG.SESSIONS_DIR
                print(f"[scan] no non-blacklisted accounts found in DB. sessions_dir={sessions_dir}")
                print("[scan] DB accounts:")
                for a in all_accounts:
                    status = "BL" if a.blacklisted else "OK"
                    print(f"  - {a.session_name} [{status}]")

            candidates = all_accounts if include_blacklisted else non_blacklisted

            if preferred_session:
                chosen = next((a for a in candidates if a.session_name == preferred_session), None)
                if not chosen:
                    print(f"[scan] preferred session '{preferred_session}' not found among candidates. Falling back.")
                else:
                    scanner_acc = chosen
            else:
                scanner_acc = candidates[0] if candidates else None

            if scanner_acc is None:
                print("[scan] no accounts found. Add a session file to data/sessions or authorize via QR."
                      " You can also pass --include-blacklisted or --session NAME")
                return

        try:
            client = await account_service.get_client(scanner_acc)
            gifts = await market_service.fetch_market(client)
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] gifts fetched: {len(gifts)}")
            for g in gifts:
                print(f"• code={g.code} title={g.title} price={g.price_stars}⭐ remaining≈{g.remaining}")
        except Exception as e:
            print("[scan] error:", e)

    async def main_cli():
        parser = argparse.ArgumentParser(description="Scan Telegram Stars gifts without running the bot")
        parser.add_argument("--watch", action="store_true", help="Continuously scan in a loop")
        parser.add_argument("--interval", type=float, default=5.0, help="Scan interval seconds when --watch is set")
        parser.add_argument("--include-blacklisted", action="store_true", help="Allow using blacklisted accounts for scanning")
        parser.add_argument("--session", type=str, default=None, help="Use specific session name (e.g., acc_default)")
        args = parser.parse_args()

        if not args.watch:
            await scan_gifts_once(include_blacklisted=args["include_blacklisted"] if isinstance(args, dict) else args.include_blacklisted,
                                  preferred_session=args["session"] if isinstance(args, dict) else args.session)
            return

        while True:
            await scan_gifts_once(include_blacklisted=args.include_blacklisted,
                                  preferred_session=args.session)
            await asyncio.sleep(args.interval)

    asyncio.run(main_cli())