from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT.parent / "data"
DB_PATH = Path(os.getenv("MARKET_CACHE_DB", str(DATA_DIR / "market_cache.sqlite3")))

TOKEN_ENV = "TUSHARE_TOKEN"
PROXY_ENV = "TUSHARE_PROXY_URL"
AI_BASE_URL_ENV = "AI_BASE_URL"
AI_API_KEY_ENV = "AI_API_KEY"
AI_MODEL_ENV = "AI_MODEL"
ADMIN_TOKEN_ENV = "ADMIN_TOKEN"
DEFAULT_PROXY_URL = ""

CACHE_TTL_SECONDS = 60 * 5
DAILY_REFRESH_AFTER = os.getenv("MARKET_REFRESH_AFTER", "15:10")
