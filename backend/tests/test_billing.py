import hashlib, hmac, json, time
from types import SimpleNamespace
import httpx, pytest
from fastapi import FastAPI, HTTPException
from backend.app.billing import Billing
from backend.app.storage import Repository, record


@pytest.fixture
async def billing(tmp_path):
    repo = Repository(f"sqlite+aiosqlite:///{tmp_path}/billing.db")
    await repo.initialize()
    calls = []

    def handler(req):
        calls.append(req)
        if req.url.path.endswith("/prices/price_test"):
            return httpx.Response(
                200,
                json={
                    "active": True,
                    "unit_amount": 9900,
                    "currency": "inr",
                    "recurring": {"interval": "month", "usage_type": "licensed"},
                },
            )
        if req.url.path.endswith("/subscriptions/sub_test"):
            return httpx.Response(
                200,
                json={
                    "id": "sub_test",
                    "metadata": {"billing_ref": "owner"},
                    "customer": "cus_test",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_test"}}]},
                },
            )
        if req.method == "POST":
            return httpx.Response(
                200,
                json={"id": "cs_test", "url": "https://checkout.stripe.com/c/pay/test"},
            )
        return httpx.Response(
            200,
            json={"status": "open", "url": "https://checkout.stripe.com/c/pay/test"},
        )

    b = Billing(repo, transport=httpx.MockTransport(handler))
    b.key = "sk_test_fixture"
    b.webhook_secret = "whsec_fixture"
    b.price_id = "price_test"
    await repo.put_many(
        [
            record(
                "billing",
                "owner",
                {
                    "id": "owner",
                    "status": "none",
                    "customer": None,
                    "subscription": None,
                },
            )
        ]
    )
    yield b, calls
    await repo.close()


def signed(event, secret="whsec_fixture", timestamp=None):
    raw = json.dumps(event).encode()
    timestamp = timestamp or int(time.time())
    digest = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    return raw, f"t={timestamp},v1={digest}"


@pytest.mark.asyncio
async def test_checkout_uses_server_price_and_reuses_pending_session(billing):
    b, calls = billing
    first = await b.checkout("owner", {})
    second = await b.checkout("owner", {})
    assert first == second
    posts = [r for r in calls if r.method == "POST"]
    assert len(posts) == 1
    assert b"price_test" in posts[0].content
    assert posts[0].headers["Idempotency-Key"].startswith("ax-")
    assert (await b.repo.get("billing", "owner"))["status"] == "none"


@pytest.mark.asyncio
async def test_verified_webhook_updates_state_and_deduplicates(billing):
    b, calls = billing
    event = {
        "id": "evt_verified",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {"object": {"subscription": "sub_test"}},
    }
    raw, signature = signed(event)
    assert (await b.webhook(raw, signature))["status"] == "processed"
    assert (await b.repo.get("billing", "owner"))["status"] == "active"
    before = len(calls)
    assert (await b.webhook(raw, signature))["status"] == "duplicate"
    assert len(calls) == before
    with pytest.raises(HTTPException) as exc:
        await b.checkout("owner", {})
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_forged_or_expired_webhook_cannot_activate(billing):
    b, _ = billing
    event = {
        "id": "evt_bad",
        "type": "customer.subscription.updated",
        "livemode": False,
        "data": {"object": {"id": "sub_test"}},
    }
    for args in [
        signed(event, "wrong"),
        signed(event, timestamp=int(time.time()) - 600),
    ]:
        with pytest.raises(HTTPException) as exc:
            await b.webhook(*args)
        assert exc.value.status_code == 400
    assert (await b.repo.get("billing", "owner"))["status"] == "none"


@pytest.mark.asyncio
async def test_billing_portal_requires_cookie_and_same_origin(billing):
    b, calls = billing
    app = FastAPI()
    app.include_router(b.router())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8080"
    ) as c:
        assert (
            await c.post("/billing/portal", headers={"Origin": "https://other.example"})
        ).status_code == 403
        assert (
            await c.post("/billing/portal", headers={"Origin": "http://localhost:8080"})
        ).status_code == 401
        r = await c.get("/billing/status")
        assert r.status_code == 200
        assert "HttpOnly" in r.headers["set-cookie"]
        assert (
            await c.post("/billing/portal", headers={"Origin": "http://localhost:8080"})
        ).status_code == 409
    assert not [r for r in calls if r.method == "POST"]


@pytest.mark.asyncio
async def test_live_mode_requires_explicit_server_enable(billing):
    b, _ = billing
    b.key = "sk_live_fixture"
    b.allow_live = False
    assert not b.configured
