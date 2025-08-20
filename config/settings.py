from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Column, DateTime
from sqlmodel import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TG_", extra="ignore")

    BOT_TOKEN: str
    ADMIN_IDS: str | None = None

    API_ID: int
    API_HASH: str
    PHONE_NUMBER: str | None = None
    SESSION_NAME: str = "default"

    COMMISSION_RATE: float = 0.10
    MAX_STARS_PER_ACCOUNT: int = 2000

    DATA_DIR: str = "./data"
    DB_PATH: str = "./data/app.db"
    DB_DSN: str | None = None
    SESSIONS_DIR: str = "./data/sessions"
    TDATA_DIR: str = "./data/tdata"
    PROXIES_FILE: str = "./data/proxies.json"
    BLACKLIST_FILE: str = "./data/blacklist.json"

    SCAN_INTERVAL_SEC: float = 5.0
    BATCH_PURCHASE_SLEEP_MS: int = 400

    STARS_CURRENCY: str = "XTR"

    PURCHASE_MODE: str = "limited"

    NOTIFY_ADMINS: bool = True

    # Login
    LOGIN_METHOD: str = "code"
    FORCE_SMS: bool = False


def ensure_dirs(cfg: Settings):
    Path(cfg.DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(cfg.SESSIONS_DIR).mkdir(parents=True, exist_ok=True)
    Path(cfg.TDATA_DIR).mkdir(parents=True, exist_ok=True)
    if not Path(cfg.PROXIES_FILE).exists():
        Path(cfg.PROXIES_FILE).write_text("{}", encoding="utf-8")
    if not Path(cfg.BLACKLIST_FILE).exists():
        Path(cfg.BLACKLIST_FILE).write_text("[]", encoding="utf-8")


CFG = Settings()  # Load .env
ensure_dirs(CFG)

ADMIN_IDS: set[int] = set()
if CFG.ADMIN_IDS:
    ADMIN_IDS = {int(x.strip()) for x in CFG.ADMIN_IDS.split(",") if x.strip().isdigit()}