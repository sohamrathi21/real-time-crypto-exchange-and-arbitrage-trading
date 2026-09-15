"""Browser-bound local subscriptions using Stripe-hosted Checkout and Portal.
Secrets never enter the frontend. Webhooks, not redirects, determine status.
"""

import asyncio
import hashlib
import json
import os
import secrets
from urllib.parse import urlparse
import httpx
import stripe
from fastapi import APIRouter, HTTPException, Request, Response
from .storage import record
from .models import now_ms


class Billing:
    def __init__(self, repository, bus=None, transport=None):
        self.repo, self.bus, self.transport = repository, bus, transport
        self.key = os.getenv("STRIPE_SECRET_KEY", "")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self.price_id = os.getenv("STRIPE_PRICE_ID", "")
        self.origin = os.getenv("BILLING_PUBLIC_URL", "http://localhost:8080").rstrip(
            "/"
        )
        self.allow_live = os.getenv("STRIPE_ALLOW_LIVE", "false").lower() == "true"
        self.lock = asyncio.Lock()

    @property
    def configured(self):
        return bool(
            self.key
            and self.webhook_secret
            and self.price_id
            and (
                self.key.startswith("sk_test_")
                or self.allow_live
                and self.key.startswith("sk_live_")
            )
        )

    async def api(self, method, path, data=None, idem=None):
        if not self.configured:
            raise HTTPException(
                503,
                "Stripe is not configured. Add the server secret key, webhook secret and recurring Price ID.",
            )
        headers = {
            "Authorization": "Bearer " + self.key,
            "Stripe-Version": "2025-02-24.acacia",
        }
        if idem:
            headers["Idempotency-Key"] = idem
        async with httpx.AsyncClient(timeout=15, transport=self.transport) as client:
            try:
                result = await client.request(
                    method,
                    "https://api.stripe.com/v1" + path,
                    data=data,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    502,
                    "Stripe did not respond. Retry safely; the same Checkout request is reused.",
                ) from exc
        if result.status_code >= 400:
            raise HTTPException(
                502,
                "Stripe rejected the request. Check server keys, recurring price, and customer portal configuration.",
            )
        return result.json()

    def guard_origin(self, request):
        if request.headers.get("origin") != self.origin:
            raise HTTPException(403, "Billing requests must originate from this app.")

    async def identity(self, request, response, create=False):
        token = request.cookies.get("ax_billing", "")
        ref = hashlib.sha256(token.encode()).hexdigest() if token else ""
        state = await self.repo.get("billing", ref) if ref else None
        if state is None and create:
            token = secrets.token_urlsafe(32)
            ref = hashlib.sha256(token.encode()).hexdigest()
            state = {
                "id": ref,
                "status": "none",
                "customer": None,
                "subscription": None,
            }
            await self.repo.put_many([record("billing", ref, state)])
            response.set_cookie(
                "ax_billing",
                token,
                httponly=True,
                secure=self.origin.startswith("https://"),
                samesite="strict",
                max_age=30 * 86400,
                path="/",
            )
        if state is None:
            raise HTTPException(
                401, "Open the subscription page to start a billing session."
            )
        return ref, state

    async def plan(self):
        p = await self.api("GET", "/prices/" + self.price_id)
        recurring = p.get("recurring") or {}
        if (
            bool(p.get("livemode")) != self.key.startswith("sk_live_")
            or not p.get("active")
            or not recurring
            or recurring.get("usage_type") == "metered"
            or p.get("unit_amount") is None
            or p["unit_amount"] <= 0
        ):
            raise HTTPException(
                503,
                "Configure an active, fixed-price recurring subscription in Stripe.",
            )
        return {
            "amount": p["unit_amount"],
            "currency": p["currency"],
            "interval": recurring["interval"],
            "interval_count": recurring.get("interval_count", 1),
            "livemode": p.get("livemode", False),
        }

    async def checkout(self, ref, state):
        async with self.lock:
            state = await self.repo.get("billing", ref)
            if state.get("status") in (
                "active",
                "trialing",
                "past_due",
                "unpaid",
                "paused",
            ):
                raise HTTPException(
                    409, "A subscription already exists. Use Manage billing."
                )
            await self.plan()
            if state.get("checkout_id"):
                current = await self.api(
                    "GET", "/checkout/sessions/" + state["checkout_id"]
                )
                if current.get("status") == "open":
                    return {"url": current["url"]}
                if current.get("status") == "complete":
                    raise HTTPException(
                        409,
                        "Checkout completed. Awaiting the verified subscription update; refresh status shortly.",
                    )
                state.pop("checkout_id", None)
                state.pop("checkout_attempt", None)
            if not state.get("checkout_attempt"):
                state["checkout_attempt"] = secrets.token_hex(16)
                await self.repo.put_many([record("billing", ref, state)])
            payload = {
                "mode": "subscription",
                "line_items[0][price]": self.price_id,
                "line_items[0][quantity]": "1",
                "success_url": self.origin + "/?billing=return#Subscription",
                "cancel_url": self.origin + "/#Subscription",
                "client_reference_id": ref,
                "metadata[billing_ref]": ref,
                "subscription_data[metadata][billing_ref]": ref,
            }
            if state.get("customer"):
                payload["customer"] = state["customer"]
            session = await self.api(
                "POST", "/checkout/sessions", payload, "ax-" + state["checkout_attempt"]
            )
            state["checkout_id"] = session["id"]
            await self.repo.put_many([record("billing", ref, state)])
            return {"url": session["url"]}

    async def webhook(self, raw, signature):
        if not self.configured:
            raise HTTPException(503, "Stripe webhook is not configured.")
        if len(raw) > 1_000_000:
            raise HTTPException(413, "Webhook too large")
        try:
            event = stripe.Webhook.construct_event(
                raw, signature, self.webhook_secret, tolerance=300
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise HTTPException(400, "Invalid Stripe signature or payload") from exc
        event = json.loads(
            raw
        )  # Parse only after the SDK verifies the exact raw bytes.
        if bool(event.get("livemode")) != self.key.startswith("sk_live_"):
            raise HTTPException(400, "Stripe event mode mismatch")
        async with self.lock:
            if await self.repo.get("stripe_event", event["id"]):
                return {"status": "duplicate"}
            kind = event["type"]
            obj = event["data"]["object"]
            sub_id = None
            if kind.startswith("customer.subscription."):
                sub_id = obj["id"]
            elif kind.startswith("checkout.session.") or kind.startswith("invoice."):
                sub_id = obj.get("subscription") or (obj.get("parent") or {}).get(
                    "subscription_details", {}
                ).get("subscription")
            state = None
            ref = None
            if sub_id:
                subscription = (
                    obj
                    if kind == "customer.subscription.deleted"
                    else await self.api("GET", "/subscriptions/" + sub_id)
                )
                ref = subscription.get("metadata", {}).get("billing_ref")
                state = await self.repo.get("billing", ref) if ref else None
                prices = [
                    i["price"]["id"]
                    for i in subscription.get("items", {}).get("data", [])
                ]
                if (
                    state
                    and state.get("subscription") not in (None, sub_id)
                    and state.get("status")
                    in ("active", "trialing", "past_due", "unpaid", "paused")
                ):
                    state = None
                if state and (
                    self.price_id in prices or state.get("subscription") == sub_id
                ):
                    state = {
                        **state,
                        "customer": subscription.get("customer"),
                        "subscription": sub_id,
                        "status": subscription.get("status", "unknown"),
                        "cancel_at_period_end": subscription.get(
                            "cancel_at_period_end", False
                        ),
                        "updated_at": now_ms(),
                    }
                    if state["status"] == "canceled":
                        state.pop("checkout_id", None)
                        state.pop("checkout_attempt", None)
                else:
                    state = None
            records = [
                record(
                    "stripe_event",
                    event["id"],
                    {"id": event["id"], "type": kind, "received_at": now_ms()},
                )
            ]
            if state:
                records.append(record("billing", ref, state))
            await self.repo.put_many(records)
            if state and self.bus:
                self.bus.emit(
                    "SUBSCRIPTION_UPDATED",
                    metadata={
                        "stripe_event_id": event["id"],
                        "subscription_status": state["status"],
                    },
                )
            return {"status": "processed" if state else "ignored"}

    def router(self):
        router = APIRouter(prefix="/billing")

        @router.get("/status")
        async def status(request: Request, response: Response):
            response.headers["Cache-Control"] = "no-store"
            if not self.configured:
                return {
                    "configured": False,
                    "status": "not_configured",
                    "mode": "test",
                    "plan": None,
                }
            _, state = await self.identity(request, response, create=True)
            return {
                "configured": True,
                "mode": "live" if self.key.startswith("sk_live_") else "test",
                "status": state["status"],
                "cancel_at_period_end": state.get("cancel_at_period_end", False),
                "has_customer": bool(state.get("customer")),
                "plan": await self.plan(),
            }

        @router.post("/checkout")
        async def checkout(request: Request, response: Response):
            self.guard_origin(request)
            ref, state = await self.identity(request, response)
            return await self.checkout(ref, state)

        @router.post("/portal")
        async def portal(request: Request, response: Response):
            self.guard_origin(request)
            _, state = await self.identity(request, response)
            if not state.get("customer"):
                raise HTTPException(
                    409,
                    "No verified Stripe customer is linked to this browser session.",
                )
            session = await self.api(
                "POST",
                "/billing_portal/sessions",
                {
                    "customer": state["customer"],
                    "return_url": self.origin + "/#Subscription",
                },
            )
            return {"url": session["url"]}

        @router.post("/webhook")
        async def webhook(request: Request):
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 1_000_000:
                    raise HTTPException(413, "Webhook too large")
            return await self.webhook(
                bytes(raw), request.headers.get("stripe-signature", "")
            )

        return router
