"""Environment-driven settings (spec section 8).

Every variable is optional: with no env at all the app boots into ``demo``
mode, serving the bundled synthetic Yeongdeok scenario, and the Stripe
endpoints answer ``billing_not_configured``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEMO_DATA_DIR = Path(__file__).resolve().parent / "demo_data"
DEFAULT_SCENARIO = DEMO_DATA_DIR / "scenario_yeongdeok.json"
DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


@dataclass
class Settings:
    """Snapshot of the environment, taken once at app creation."""

    mode: str = "demo"  # "demo" | "live"
    firms_map_key: str = ""
    prediction_file: str = ""
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_monthly: str = ""
    stripe_price_yearly: str = ""
    db_path: str = "guardian.db"
    cors_origins: str = "*"
    scenario_path: Path = field(default_factory=lambda: DEFAULT_SCENARIO)
    tile_url: str = DEFAULT_TILE_URL
    # Demo replay pacing: 1 real minute = 5 scenario minutes (spec section 4).
    demo_time_compression: float = 5.0
    # SSE cadence (spec section 5 + demo-mode refresh).
    sse_heartbeat_seconds: float = 15.0
    sse_refresh_seconds: float = 10.0

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "*").strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def billing_configured(self) -> bool:
        return bool(self.stripe_secret_key)


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Build Settings from ``env`` (defaults to ``os.environ``).

    ``WFG_APP_MODE`` wins when set; otherwise mode is ``live`` iff
    ``WFG_FIRMS_MAP_KEY`` is present (spec section 8).
    """
    e = os.environ if env is None else env
    firms_key = e.get("WFG_FIRMS_MAP_KEY", "").strip()
    mode = e.get("WFG_APP_MODE", "").strip().lower()
    if mode not in ("demo", "live"):
        mode = "live" if firms_key else "demo"
    return Settings(
        mode=mode,
        firms_map_key=firms_key,
        prediction_file=e.get("WFG_PREDICTION_FILE", "").strip(),
        stripe_secret_key=e.get("STRIPE_SECRET_KEY", "").strip(),
        stripe_publishable_key=e.get("STRIPE_PUBLISHABLE_KEY", "").strip(),
        stripe_webhook_secret=e.get("STRIPE_WEBHOOK_SECRET", "").strip(),
        stripe_price_monthly=e.get("STRIPE_PRICE_MONTHLY", "").strip(),
        stripe_price_yearly=e.get("STRIPE_PRICE_YEARLY", "").strip(),
        db_path=e.get("WFG_DB_PATH", "guardian.db").strip() or "guardian.db",
        cors_origins=e.get("WFG_CORS_ORIGINS", "*").strip() or "*",
        scenario_path=Path(e.get("WFG_SCENARIO_FILE", "").strip() or DEFAULT_SCENARIO),
    )
