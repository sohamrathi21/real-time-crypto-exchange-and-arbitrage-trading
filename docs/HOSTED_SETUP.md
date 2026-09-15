# Hosted deployment and account setup

## Running on Vercel
- Frontend: all existing screens, light/dark themes, IST, news-channel directory and browser-only Arbitrage demo.
- Python read-only API: live exchange order books, quant opportunity checks, publisher news, Indian stock catalog and optional Kite quotes.
- Quote requests poll automatically; upstream failures stay visible. No synthetic fallback.
- Public hosted API rejects account/trading mutations. Local Docker functionality is retained.

## Enable accounts
1. Create a Supabase project; enable email/password authentication and email confirmation.
2. Set Site URL to https://real-time-crypto-exchange-and-arbit.vercel.app and allow that URL plus /?recovery=1 as redirect URLs.
3. In Vercel, set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY from the project Connect dialog. Use only the public publishable key, never the service-role secret.
4. Configure production email delivery and appropriate rate limits in Supabase.
5. Redeploy. Test registration, confirmation, login, password reset and logout with an owner-controlled test account.

The prepared interface uses the official Supabase SDK, PKCE, session refresh and provider-managed passwords. No account is created when configuration is missing. Authentication alone does not authorize billing or trading; those services still require server-side user ownership checks.

## Full persistent services
Vercel's read-only functions do not replace the local Docker services. To operate saved paper orders, replay records, n8n workflows and continuous scanning online, provision an always-running container host plus PostgreSQL and Redis using the existing compose.yml/docker-compose.yml configuration. No paid host has been provisioned.
Before exposing those local mutation APIs to multiple users, enforce verified authentication and per-user ownership on orders, portfolio, reports, replay and automation controls. The existing local engine is single-workspace software and is not tenant-isolated.

Stripe requires merchant approval, secret key, recurring price and webhook configuration. Kite requires authorized broker credentials and appropriate market-data display permissions. LLM features require a separate provider API account. None are activated by the account interface.

## Maintaining the Vercel bundle
Run `python tools/sync_hosted.py` whenever changing the shared backend files. `backend/tests/test_hosted.py` checks source parity, failed feeds, API JSON responses, empty deployment settings and the mutation guard.
