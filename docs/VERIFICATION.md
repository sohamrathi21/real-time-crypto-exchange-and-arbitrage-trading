# Review and verification

Updated 15 September 2026. Local project: http://localhost:8080. n8n: http://localhost:5678.

- 33 backend tests passed, including RSS URL validation, XML entity rejection, and cached-feed behavior during publisher outages.
- TypeScript compilation and frontend production build passed.
- Docker engine 29.8.0, WSL 2.7.14, n8n 2.38.7 installed. PostgreSQL and Redis health checks passed.
- Five n8n workflows imported; three core workflows published. A test subscription event returned HTTP 200 from n8n and its callback was observed in the backend audit events. Fixed missing webhook IDs that had previously caused prefixed routes and HTTP 404.
- Earlier browser checks: market paper buy, pending limit buy cancellation, instrument search, order-book streaming, theme persistence, and narrow-screen layout.
- Public REST feeds successfully returned BTC/ETH/SOL books from Binance, Coinbase and Kraken during local checks; OKX/Bybit were unavailable. Default market engine remains DEMO.
- Recorded demo-session backtest returned HTTP 200. Historical results are simulated, not evidence of achievable live returns.

## News, regions, real orders

News uses BBC and CoinDesk publisher RSS feeds with a five-minute cache. Source links and publication timestamps are preserved. No simulated headlines are substituted. Region feeds include general news. Calendar cards show indicative regular weekday windows, DST-aware local clocks and IST conversions; they are not holiday-aware exchange-open signals.

Zerodha trading uses the official offsite order basket: https://kite.trade/docs/connect/v3/basket/. The user enters a public Kite app API key, prepares a stock order and completes login/review/placement in Kite. No API secret, access token, account holdings, quotes, or execution status is loaded into the app by this flow. A live broker order has not been submitted or verified. Public API key and broker-side app setup are still required.

GitHub and Vercel publishing are on hold at the user's request.

## Local image build when npm registry downloads stall

Build the frontend locally, then `docker build --target prebuilt -t gapsignal-frontend ./frontend` and `docker compose up -d --no-build`. The default frontend Dockerfile retains its normal source-build path. The prebuilt target packages the same verified Vite production output.

Stripe: five additional tests verify Checkout reuse, signed webhook processing, duplicate suppression, rejected forged/expired signatures, cookie/origin requirements, and live-mode guard. The Stripe account/price/webhook settings are still required; no actual subscription payment has been run. See BILLING.md.

## Discovery home and broadcaster directory — 15 September 2026

The local Home page now includes an original market illustration, product navigation, workflow details, an illustrative contribution calculator, FAQs and links into existing modules. White/slate/teal styling supports persistent light and dark themes. Market News adds the user's 20 selected broadcaster links with regional and text filters above the existing publisher RSS headlines. Broadcaster access conditions vary; directory links do not imply embedded or free streams.

Validation: TypeScript and Vite production build passed; local Docker frontend refreshed. Browser checks confirmed light/dark rendering, 390px mobile layout, all 20 channels, India filtering to five channels and NDTV search to one. Publisher headlines loaded with IST timestamps. No external deployment or financial transaction performed.

## Final trade review update

Arbitrage rows now show Trade. The opportunity drawer contains separate Buy/Sell links to allowlisted official exchange websites, with explicit disclosure that they neither submit nor prefill orders. Links require a current live opportunity, connected stream, and timestamp no older than five seconds. Existing paper execution remains separate. Stripe remains an app-subscription integration; no trading-fund payment flow was added. No broker/exchange orders or Stripe payments were performed.

Validation: 35 backend tests, TypeScript check, production frontend build and 8 server-rendered TradeReview checks passed. Local API reported live mode with 15 live quote entries. Indian stock catalog contains 20 entries, all unavailable until Kite credentials are configured. Browser confirmed the final local Arbitrage view; no opportunity currently passed risk filters, so no live Trade row could be clicked. LLM and API options are documented in CONNECTIONS.md; no LLM is activated.

## Interactive hackathon demo

Arbitrage includes a frontend-only synthetic buy/sell demonstration, available independently of the market-data connection. Start with 5,000 USDT at each venue and 0.05 BTC at Venue B. Buy 0.01 BTC for 600 USDT plus 0.6 fee, then sell at 60,600 less 0.606 fee: net 4.794 USDT. The adverse scenario sells at 59,800 and realizes -3.198 USDT. Quantities 0.001/0.01/0.02 are selectable; wallet balances, fees and execution log update. Buttons enforce buy before sell and prevent duplicate execution. Reset restores starting funds. State is intentionally session-only and separate from the paper portfolio.

Ledger checks passed for both scenarios, inventory conservation, duplicate actions and quantity limits. Browser clicks verified the full profitable and adverse flows; reset left the demo ready for presentation. No real funds, orders or Stripe calls involved.

## Continuous live arbitrage monitor and Home startup

Every fresh document load now replaces the hash with Home while preserving query parameters. In-app navigation continues normally. Browser verified opening an Arbitrage URL starts at Home, then navigation to Arbitrage works.

Arbitrage now contains a continuous monitor driven by the existing WebSocket snapshots (~one scan/second, provider-dependent quote cadence). It compares buy asks and sell bids at distinct venues for the same symbol and quote currency. Only live, fresh quotes participate; stale, synthetic, mismatched-currency and invalid/future quotes are excluded. Gross differences are explicitly before costs. Trade is available only when a matching server-qualified opportunity exists. Disconnections pause the comparison table. Connection states, quote ages, latest scan time in IST and freshness counts are visible.

TypeScript, production build and live comparison checks passed. Browser confirmed 3 live BTC/ETH/SOL comparisons, changing venue quotes, five connected exchange statuses and current IST timestamps; no route qualified after costs/risk checks at verification time. Indian live quotes remain unconfigured and are not claimed as live.
