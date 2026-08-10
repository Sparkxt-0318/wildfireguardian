"""Shared fixtures.  Tests run offline, demo mode, no Stripe keys by default."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from guardian_app.main import create_app  # noqa: E402

# Reference user locations against the committed synthetic scenario
# (fire origin SW of 36.42N 129.37E, running NE):
FAR = (36.00, 129.00)     # ~53 km from the fire: SAFE at any t
NEAR = (36.44, 129.45)    # downwind corridor: WATCH at t=0, GO at t=200
AHEAD = (36.43, 129.48)   # further downwind: GO at t=200 with a walkable route
SOUTH = (36.37, 129.40)   # south flank: wind not toward user


@pytest.fixture()
def app(tmp_path):
    return create_app({"WFG_DB_PATH": str(tmp_path / "guardian.db")})


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def billing_app(tmp_path):
    return create_app(
        {
            "WFG_DB_PATH": str(tmp_path / "guardian-billing.db"),
            "STRIPE_SECRET_KEY": "sk_test_dummy",
            "STRIPE_PUBLISHABLE_KEY": "pk_test_dummy",
            "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
            "STRIPE_PRICE_MONTHLY": "price_month_dummy",
            "STRIPE_PRICE_YEARLY": "price_year_dummy",
        }
    )


@pytest.fixture()
def billing_client(billing_app):
    return TestClient(billing_app)
