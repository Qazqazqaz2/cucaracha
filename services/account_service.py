from config.settings import CFG
from database.engine import engine
from database.repositories.account_repo import AccountRepository
from sqlmodel import Session
from telethon import TelegramClient
from pathlib import Path
from typing import Dict
import json
import urllib.parse as up
from telethon.errors import SessionPasswordNeededError, FloodWaitError, CodeInvalidError
import asyncio
import secrets

from models.account import Account

try:
    import qrcode
except ImportError:
    qrcode = None

from utils.helpers import generate_session_name

class AccountService:
    def __init__(self):
        self.cfg = CFG
        self.clients: Dict[int, TelegramClient] = {}
        self.blacklist = self._load_blacklist()
        self.proxy_map = self._load_proxies()

    def _load_blacklist(self) -> set[str]:
        try:
            return set(json.loads(Path(self.cfg.BLACKLIST_FILE).read_text("utf-8")))
        except Exception:
            return set()

    def _save_blacklist(self):
        Path(self.cfg.BLACKLIST_FILE).write_text(json.dumps(sorted(self.blacklist), ensure_ascii=False, indent=2), "utf-8")

    def _load_proxies(self) -> dict[str, str]:
        try:
            return json.loads(Path(self.cfg.PROXIES_FILE).read_text("utf-8"))
        except Exception:
            return {}

    async def scan_sessions(self):
        with Session(engine) as s:
            repo = AccountRepository(s)
            files = list(Path(self.cfg.SESSIONS_DIR).glob("*.session"))
            for p in files:
                name = p.stem
                acc = repo.get_or_create_account(name)
                # Respect blacklist but still ensure DB entry exists
                if name in self.blacklist:
                    acc.blacklisted = True
                    if not acc.last_error:
                        acc.last_error = "blacklisted"
                if acc.proxy is None:
                    acc.proxy = self.proxy_map.get(name)
                repo.update(acc)
            # Create a default account if none found, using phone or fallback to configured session name
            if not files:
                session_name = generate_session_name(phone=self.cfg.PHONE_NUMBER, username=self.cfg.SESSION_NAME)
                acc = repo.get_or_create_account(session_name)
                if acc.proxy is None:
                    acc.proxy = self.proxy_map.get(session_name)
                    repo.update(acc)

    async def get_client(self, acc: Account) -> TelegramClient:
        if acc.id in self.clients:
            return self.clients[acc.id]

        session_base_path = Path(self.cfg.SESSIONS_DIR) / acc.session_name
        kwargs = {}
        if acc.proxy:
            u = up.urlparse(acc.proxy)
            if u.scheme.startswith("socks"):
                kwargs["proxy"] = ("socks5", u.hostname, u.port, True, u.username, u.password)

        client = TelegramClient(
            session=str(session_base_path),
            api_id=self.cfg.API_ID,
            api_hash=self.cfg.API_HASH,
            **kwargs
        )

        await client.connect()

        if not await client.is_user_authorized():
            use_qr = (self.cfg.LOGIN_METHOD.lower() == "qr") or not self.cfg.PHONE_NUMBER
            if use_qr:
                print("Включена авторизация по QR-коду. Отсканируйте QR в приложении Telegram (Настройки → Устройства).")
                try:
                    qr_login = await client.qr_login()
                    try:
                        if qrcode:
                            qr = qrcode.QRCode(border=1)
                            qr.add_data(qr_login.url)
                            qr.make(fit=True)
                            qr.print_ascii(invert=True)
                        else:
                            print(f"QR URL: {qr_login.url}")
                        print("Ожидаю сканирования...")
                        await qr_login.wait()
                        print("Авторизация завершена через QR.")
                    except SessionPasswordNeededError:
                        pwd = input("Введите пароль 2FA: ")
                        await client.sign_in(password=pwd)
                    except FloodWaitError as e:
                        print(f"Флуд-ограничение: подождите {e.seconds} секунд.")
                        await asyncio.sleep(e.seconds)
                except Exception as e:
                    raise RuntimeError(f"QR-авторизация не удалась: {e}")
            else:
                if not self.cfg.PHONE_NUMBER:
                    raise RuntimeError("Нужен TG_PHONE_NUMBER в .env или установите TG_LOGIN_METHOD=qr для авторизации по QR.")

                authorized = False
                while not authorized:
                    try:
                        await client.send_code_request(self.cfg.PHONE_NUMBER, force_sms=self.cfg.FORCE_SMS)
                        code = input(f"Введите код из Telegram для {self.cfg.PHONE_NUMBER}: ")

                        try:
                            await client.sign_in(self.cfg.PHONE_NUMBER, code)
                            authorized = True
                        except SessionPasswordNeededError:
                            pwd = input("Введите пароль 2FA: ")
                            await client.sign_in(password=pwd)
                            authorized = True
                        except CodeInvalidError:
                            print("Неверный код. Повторите попытку.")
                        except FloodWaitError as e:
                            print(f"Флуд-ограничение: подождите {e.seconds} секунд.")
                            await asyncio.sleep(e.seconds)
                        except Exception as e:
                            print(f"Ошибка авторизации: {e}. Повторите попытку.")
                    except Exception as e:
                        print(f"Ошибка при запросе кода: {e}. Повторите попытку позже.")
                        await asyncio.sleep(10)

        self.clients[acc.id] = client
        return client

    async def blacklist_account(self, acc: Account, reason: str, repo: AccountRepository):
        repo.blacklist(acc, reason)
        self.blacklist.add(acc.session_name)
        self._save_blacklist()