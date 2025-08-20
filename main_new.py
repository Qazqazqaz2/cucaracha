import asyncio
import contextlib
import signal
from config.settings import CFG
from services.market_service import MarketService
from services.account_service import AccountService
from services.purchase_service import PurchaseService
from bot.dispatcher import bot, dp
from bot.handlers.user_handlers import *
from bot.handlers import user_handlers  # avoid shadowing top-level 'bot' name
from bot.handlers import admin_handlers  # ensure admin routes are registered

market_service = MarketService()
account_service = AccountService()
purchase_service = PurchaseService(market_service, account_service)
user_handlers.purchase_service = purchase_service  # wire service into handlers

async def main():
    worker = asyncio.create_task(purchase_service.purchase_loop())
    delivery = asyncio.create_task(purchase_service.delivery_loop())

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _stop():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _stop)

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
        await stop_event.wait()
    finally:
        worker.cancel()
        delivery.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
            await delivery


if __name__ == "__main__":
    asyncio.run(main())