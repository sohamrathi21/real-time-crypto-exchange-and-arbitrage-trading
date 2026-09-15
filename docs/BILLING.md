# Stripe subscription setup

The local Subscription page uses Stripe-hosted Checkout and Customer Portal. It has no card-number fields. No payment has been taken, and no price is invented in the application.

## Configure a Stripe sandbox

1. In Stripe, create a product and one active, fixed-price recurring Price. Choose the currency, amount and billing interval there.
2. Put `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, and `STRIPE_WEBHOOK_SECRET` in the repository's ignored `.env`. Use a test secret key first. Keep `STRIPE_ALLOW_LIVE=false`.
3. Keep `BILLING_PUBLIC_URL=http://localhost:8080` for this preview. Open that exact origin for billing.
4. Configure Customer Portal in the Stripe Dashboard.
5. Forward Stripe events to `http://localhost:8000/billing/webhook` using the authenticated Stripe CLI (`stripe listen --forward-to localhost:8000/billing/webhook`). Put that listener's signing secret in `.env`; it differs from a Dashboard endpoint's secret.
6. Recreate the backend: `docker compose up -d --no-deps backend`.
7. Open Subscription. The amount/interval should match Stripe. Use test Checkout and verify a signed `checkout.session.completed` / `customer.subscription.updated` event updates status. Test renewal (`invoice.paid`), failure (`invoice.payment_failed`) and cancellation (`customer.subscription.deleted`) events.

## Event flow

Stripe → signature-verified backend webhook → persisted subscription state → `SUBSCRIPTION_UPDATED` event → local n8n workflow → terminal notification.

The backend retrieves current subscription state from Stripe before updating most events so delayed webhook delivery does not blindly overwrite newer status. Event IDs are persisted to ignore duplicate delivery. Checkout uses a persisted idempotency key and reuses an open Checkout Session. A return URL is never treated as payment proof. Payment events contain no card data in application storage.

## Scope and prerequisites

- The current application is a local, single-process preview. Billing identity is an opaque HttpOnly browser cookie; Stripe customer IDs are never accepted from the browser. Portal access requires that cookie and a matching request origin.
- Losing that browser cookie loses this local billing association. A production account/login system, cross-device recovery and subscription-based feature authorization must be completed before monetizing a public multi-user app. Existing preview features are not paywalled.
- No Stripe account, key, recurring price or real Checkout session has been configured in this workspace. Tests use simulated Stripe API responses and SDK-verified signed test payloads.
- Live keys are rejected unless `STRIPE_ALLOW_LIVE=true` is explicitly configured. This is not needed for local testing.
- GitHub and Vercel publishing remain on hold.

## Official references

- [Stripe Checkout subscriptions](https://docs.stripe.com/billing/subscriptions/build-subscriptions)
- [Webhook signature verification](https://docs.stripe.com/webhooks/signature)
- [Customer Portal](https://docs.stripe.com/customer-management/integrate-customer-portal)
