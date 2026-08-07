"""Stripe billing endpoints.

Runs with NO keys and NO network: the unconfigured cases hit the real code
paths, the configured cases stub the ``stripe`` module with monkeypatch.
"""

from __future__ import annotations

import stripe

CHECKOUT_BODY = {
    "plan": "monthly",
    "success_url": "https://app.example/ok",
    "cancel_url": "https://app.example/cancel",
}


# ------------------------------------------------- not configured (no keys) --


def test_checkout_billing_not_configured(client):
    r = client.post("/v1/billing/checkout", json=CHECKOUT_BODY)
    assert r.status_code == 503
    j = r.json()
    assert j["error"] == "billing_not_configured"
    assert j["detail_ko"] and j["detail_en"]


def test_webhook_billing_not_configured(client):
    r = client.post("/v1/billing/webhook", content=b"{}")
    assert r.status_code == 503
    assert r.json()["error"] == "billing_not_configured"


def test_status_billing_not_configured(client):
    r = client.get("/v1/billing/status?customer_id=cus_x")
    assert r.status_code == 200
    assert r.json() == {"active": False, "reason": "billing_not_configured"}


# ------------------------------------------- configured, stripe stubbed out --


def test_checkout_returns_hosted_url(billing_client, monkeypatch):
    class FakeSession:
        url = "https://checkout.stripe.com/c/pay/fake_session"

    created = {}

    def fake_create(**kwargs):
        created.update(kwargs)
        return FakeSession()

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)
    r = billing_client.post("/v1/billing/checkout", json=CHECKOUT_BODY)
    assert r.status_code == 200
    assert r.json() == {"checkout_url": FakeSession.url}
    assert created["mode"] == "subscription"
    assert created["line_items"][0]["price"] == "price_month_dummy"


def test_checkout_yearly_uses_yearly_price(billing_client, monkeypatch):
    created = {}

    def fake_create(**kwargs):
        created.update(kwargs)
        return type("S", (), {"url": "https://checkout.stripe.com/x"})()

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)
    r = billing_client.post("/v1/billing/checkout", json={**CHECKOUT_BODY, "plan": "yearly"})
    assert r.status_code == 200
    assert created["line_items"][0]["price"] == "price_year_dummy"


def test_webhook_rejects_bad_signature(billing_client, monkeypatch):
    def fake_construct_event(payload, sig_header, secret):
        raise ValueError("signature verification failed")

    monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct_event)
    r = billing_client.post(
        "/v1/billing/webhook",
        content=b'{"type":"checkout.session.completed"}',
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert r.status_code == 400
    j = r.json()
    assert j["error"] == "invalid_signature"
    assert j["detail_ko"] and j["detail_en"]


def test_webhook_verified_event_activates_subscription(billing_client, monkeypatch):
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_test_1",
                "subscription": "sub_test_1",
                "metadata": {"plan": "monthly"},
            }
        },
    }

    monkeypatch.setattr(
        stripe.Webhook, "construct_event", lambda payload, sig, secret: event
    )
    r = billing_client.post(
        "/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=ok"}
    )
    assert r.status_code == 200
    assert r.json() == {"received": True}

    j = billing_client.get("/v1/billing/status?customer_id=cus_test_1").json()
    assert j["active"] is True
    assert j["plan"] == "monthly"
    assert "renews_utc" in j


def test_webhook_subscription_deleted_deactivates(billing_client, monkeypatch):
    completed = {
        "type": "checkout.session.completed",
        "data": {"object": {"customer": "cus_test_2", "subscription": "sub_2",
                            "metadata": {"plan": "yearly"}}},
    }
    deleted = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"customer": "cus_test_2", "id": "sub_2", "status": "canceled"}},
    }
    events = iter([completed, deleted])
    monkeypatch.setattr(
        stripe.Webhook, "construct_event", lambda payload, sig, secret: next(events)
    )
    for _ in range(2):
        r = billing_client.post(
            "/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
        )
        assert r.status_code == 200
    j = billing_client.get("/v1/billing/status?customer_id=cus_test_2").json()
    assert j["active"] is False


def test_status_unknown_customer_inactive(billing_client):
    j = billing_client.get("/v1/billing/status?customer_id=cus_nobody").json()
    assert j == {"active": False, "plan": None, "renews_utc": None}
