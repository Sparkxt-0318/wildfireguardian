"""Stripe billing: hosted Checkout, signature-verified webhook, status (spec §9).

Card data never touches this backend — Checkout is Stripe-hosted.  With no
``STRIPE_SECRET_KEY`` configured every billing endpoint degrades honestly:
checkout/webhook answer 503 ``billing_not_configured`` and status reports
``{"active": false, "reason": "billing_not_configured"}``.  Life-safety
endpoints never depend on any of this (spec §1: safety is free, forever).
"""

from __future__ import annotations

import stripe
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .models import CheckoutRequest

router = APIRouter()

_NOT_CONFIGURED = {
    "error": "billing_not_configured",
    "detail_ko": "결제 기능이 아직 설정되지 않았습니다. 안전 기능은 모두 무료로 계속 사용하실 수 있습니다.",
    "detail_en": "Billing is not configured. All safety features remain free and fully available.",
}


def _settings(request: Request):
    return request.app.state.settings


def _store(request: Request):
    return request.app.state.store


@router.post("/billing/checkout")
async def create_checkout(request: Request, body: CheckoutRequest):
    settings = _settings(request)
    if not settings.billing_configured:
        return JSONResponse(status_code=503, content=_NOT_CONFIGURED)
    price = (
        settings.stripe_price_yearly if body.plan == "yearly" else settings.stripe_price_monthly
    )
    if not price:
        return JSONResponse(
            status_code=503,
            content={
                "error": "billing_not_configured",
                "detail_ko": "요금제가 아직 설정되지 않았습니다.",
                "detail_en": "The requested plan's price is not configured.",
            },
        )
    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price, "quantity": 1}],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except Exception:
        return JSONResponse(
            status_code=502,
            content={
                "error": "stripe_error",
                "detail_ko": "결제 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                "detail_en": "Could not reach the payment service. Please try again shortly.",
            },
        )
    return {"checkout_url": session.url}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    settings = _settings(request)
    if not settings.billing_configured or not settings.stripe_webhook_secret:
        return JSONResponse(status_code=503, content=_NOT_CONFIGURED)
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception:
        # Bad payload or bad/missing signature: reject, never process.
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_signature",
                "detail_ko": "웹훅 서명을 확인하지 못했습니다.",
                "detail_en": "Webhook signature verification failed.",
            },
        )

    etype = event["type"]
    data = event["data"]["object"]
    store = _store(request)
    if etype == "checkout.session.completed":
        customer_id = data.get("customer")
        if customer_id:
            store.upsert_subscription(
                customer_id,
                subscription_id=data.get("subscription"),
                plan=(data.get("metadata") or {}).get("plan"),
                status="active",
            )
    elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = data.get("customer")
        if customer_id:
            status = data.get("status", "canceled")
            active = etype != "customer.subscription.deleted" and status in (
                "active",
                "trialing",
            )
            renews = data.get("current_period_end")
            renews_utc = None
            if isinstance(renews, (int, float)):
                from datetime import datetime, timezone

                renews_utc = datetime.fromtimestamp(renews, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            store.upsert_subscription(
                customer_id,
                subscription_id=data.get("id"),
                plan=(data.get("metadata") or {}).get("plan"),
                status="active" if active else "canceled",
                renews_utc=renews_utc,
            )
    return {"received": True}


@router.get("/billing/status")
async def billing_status(request: Request, customer_id: str = ""):
    settings = _settings(request)
    if not settings.billing_configured:
        return {"active": False, "reason": "billing_not_configured"}
    sub = _store(request).get_subscription(customer_id) if customer_id else None
    if not sub or sub.get("status") != "active":
        return {"active": False, "plan": None, "renews_utc": None}
    return {"active": True, "plan": sub.get("plan"), "renews_utc": sub.get("renews_utc")}
