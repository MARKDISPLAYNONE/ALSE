"""Environment-driven settings (Doc 4 §1.1: secrets only via .env, never in code)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var {name} — see .env.example")
    return v


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_key: str
    discord_webhook: str
    discord_critical_webhook: str
    mt5_login: str
    mt5_password: str
    mt5_server: str
    mt5_symbol: str
    mt5_mode: str
    mt5_bridge_host: str
    mt5_bridge_port: int
    env: str
    buffer_dir: Path
    health_port: int

    @classmethod
    def load(cls, require_mt5: bool = True) -> Settings:
        g = os.getenv
        return cls(
            supabase_url=_req("SUPABASE_URL").rstrip("/"),
            supabase_service_key=_req("SUPABASE_SERVICE_ROLE_KEY"),
            discord_webhook=_req("DISCORD_WEBHOOK_URL"),
            discord_critical_webhook=g("DISCORD_CRITICAL_WEBHOOK_URL", "") or _req("DISCORD_WEBHOOK_URL"),
            mt5_login=_req("MT5_LOGIN") if require_mt5 else g("MT5_LOGIN", ""),
            mt5_password=_req("MT5_PASSWORD") if require_mt5 else g("MT5_PASSWORD", ""),
            mt5_server=_req("MT5_SERVER") if require_mt5 else g("MT5_SERVER", ""),
            mt5_symbol=g("MT5_SYMBOL", "UT100xx"),
            mt5_mode=g("MT5_MODE", "bridge"),
            mt5_bridge_host=g("MT5_BRIDGE_HOST", "127.0.0.1"),
            mt5_bridge_port=int(g("MT5_BRIDGE_PORT", "18812")),
            env=g("ALSE_ENV", "demo"),
            buffer_dir=Path(g("ALSE_BUFFER_DIR", "./buffer")),
            health_port=int(g("ALSE_HEALTH_PORT", "8080")),
        )
