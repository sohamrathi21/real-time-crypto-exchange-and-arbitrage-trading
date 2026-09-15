# Market data and AI connections

## Configured locally
- Crypto uses the existing public Binance, Coinbase, Kraken, OKX and Bybit adapters. Each venue reports availability separately. Live mode no longer substitutes artificial order books when a venue fails.
- Indian Stocks contains 20 curated NSE companies. The server-only Kite quote adapter polls on request with a ten-second cache. Set KITE_API_KEY and KITE_ACCESS_TOKEN in a gitignored root .env and recreate backend. Tokens require renewal through Kite authentication. No keys are sent to the frontend. No actual Indian prices are supplied until connected.
- Publisher news feeds continue separately.

## Recommended next services (checked 15 September 2026)
- Zerodha Kite Connect: retail data subscription ₹500 per app/month; matches existing Kite order-review integration. Personal free plan excludes market data. https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/what-are-the-charges-for-kite-apis
- Upstox: alternative advertising free trading and market-data APIs. Requires its own account/app authorization. Business integrations should contact Upstox. https://upstox.com/trading-api/
- OpenAI Responses API: use one economical text model for evidence-grounded summaries and research Q&A; choose an available model after configuring an API account and budget. https://developers.openai.com/api/docs/pricing
- Gemini API: alternative with model-dependent free tiers for prototyping and usage-based paid plans. Check data-use terms before sending private financial information. https://ai.google.dev/gemini-api/docs/pricing

No LLM credentials, billing account or model has been configured. No paid API subscription was purchased. This recommendation does not activate an LLM. Broker data access does not automatically grant rights to redistribute quotes in a public subscription product; obtain provider approval for that use before launch.

All monetary calculations remain deterministic. AI should cite supplied sources, expose timestamps and uncertainty, and never invent missing quotes or place orders.
