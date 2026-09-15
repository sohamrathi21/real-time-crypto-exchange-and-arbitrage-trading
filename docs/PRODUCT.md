# ARBITRAGE X — product overview

## Purpose

A local market intelligence workspace for comparing exchange order books, evaluating depth-based arbitrage, practicing paper trading, reading publisher news, and preparing Zerodha orders for review in Kite.

## Features and current status

| Module | What it does | Current limit |
|---|---|---|
| Terminal and markets | Search instruments, charts, watchlists and order-book depth | Default feed is clearly labeled DEMO |
| Live crypto adapters | Public Binance, Coinbase, Kraken, OKX and Bybit feeds | Availability varies; fallback is labeled |
| Arbitrage | Cross-venue and triangular routes with depth VWAP, fees, slippage, risk and confidence | Execution uses the paper engine; prefunded inventory is assumed |
| Paper trading | Market/limit orders, positions, cancellation and P&L | No real broker order is sent |
| Replay/backtest | Replays recorded book snapshots through the detector | Simulated results do not predict live performance |
| Market News | Actual BBC and CoinDesk RSS headlines with source links and timestamps | Five-minute polling; some regional feeds cover broader news |
| Continents | Regional sessions, local clocks and IST conversion | Indicative weekdays; holidays and halts require exchange calendar verification |
| Live Trading | Zerodha's official offsite order basket for NSE/BSE equities | Public Kite app key required; user places the order in Kite; account data is not synced |
| Subscription | Stripe Checkout, Customer Portal, signed webhook status, n8n notifications | Stripe account settings required; no payments have been run |
| Automation | n8n event workflows, health checks, reports and guarded paper requests | External messaging credentials are optional and unconfigured |
| Themes/time | Persistent dark/light themes based on the supplied visual reference | Main timestamps use Asia/Kolkata; regional clocks name their local city |

## Technology

- React 19, TypeScript, Vite, Tailwind CSS, Recharts, Lucide icons.
- Python 3.12, FastAPI, WebSockets, Pydantic, SQLAlchemy, HTTPX.
- PostgreSQL 16 and Redis 7; SQLite is available for a native local backend.
- Docker Desktop with WSL 2, Docker Compose, Nginx, n8n 2.38.7.
- Stripe's official Python SDK verifies webhook signatures. Zerodha integration follows the official offsite basket documentation.
- pytest, TypeScript compilation, production builds and browser interaction checks verify behavior.

## Local URLs

- App: http://localhost:8080
- n8n: http://localhost:5678
- Backend health: http://localhost:8000/health

## Deployment and production scope

Nothing has been published to GitHub or Vercel. This is a single-user local preview. A public multi-user product still needs account authentication, authorization, subscription access controls, secret management and a persistent backend host. Stripe and Zerodha account configuration are required for their external services. No real trade or charge was executed during development or verification.
