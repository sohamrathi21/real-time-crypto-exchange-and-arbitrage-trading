# n8n Community Edition — local automation

No paid n8n Cloud account is required. n8n is an optional event orchestration service; no market tick or VWAP computation passes through it.

## Start and import

1. Run `docker compose up --build` from the repository root.
2. Open http://localhost:5678 and complete n8n's local owner setup.
3. Import the JSON files from `automation/workflows` using the n8n editor's **Import from file**. Alternatively, `docker compose exec n8n n8n import:workflow --separate --input=/workflows` imports the mounted files. Imported workflows are inactive until published/activated.
4. Activate **High confidence + guarded paper orchestration**, **Market health monitor**, and **Session report**. The two other webhooks are optional standalone alternatives.
5. Backend `N8N_WEBHOOK_URL` must be `http://n8n:5678/webhook/arbitrage-x-events` inside Compose. For a native backend, use `http://localhost:5678/webhook/arbitrage-x-events`.
6. Match `AUTOMATION_TOKEN` (backend) and `ARBITRAGE_AUTOMATION_TOKEN` (n8n). Compose supplies a local demo default. Replace it before any public use. Never put this token into frontend variables.
7. In ARBITRAGE X → Automation, verify the delivery state. It becomes CONNECTED only after a successful HTTP delivery. A 404 usually means the workflow is not active or the production webhook path differs.

n8n's own workflow database uses its local persistent volume; application reports, notifications, trades, and audit events use the app's PostgreSQL connection. The service binds to localhost. Do not expose its editor publicly without authentication/TLS and hardened settings.

## Workflows

| File | Trigger | Result |
|---|---|---|
| high-confidence-alert.json | Engine webhook | Validates token and edge/confidence/liquidity, stores local notification, requests guarded paper execution |
| auto-paper-trade.json | Optional dedicated webhook | Sends idempotent request to final Python validation |
| market-health.json | Every minute | Reads provider/infrastructure health and stores a local notification |
| session-report.json | Every 15 minutes | Calls Python to calculate and persist the session report |
| system-alert.json | Optional system webhook | Validates token and persists a local system notification |

The default alert workflow uses 0.15% edge, 85 confidence, and 60 liquidity; change its gate if your workflow needs a different alert policy. Python always enforces the currently configured server thresholds as well. A callback while auto paper trading is OFF returns 409; the workflow deliberately continues without executing anything. This is expected, not a real trade failure.

## Local and optional external notifications

Local notifications require no external credentials. The callback `/automation/notify` persists the original event ID and deduplicates repeated workflow deliveries.

To add external channels, connect the validated event output in the n8n editor to one of its built-in nodes. These remain optional and disabled until configured:

- **Telegram:** Telegram node → Send Message; create a bot-token credential and choose a chat you control.
- **Discord:** Discord node or HTTP Request to your Discord webhook; store the webhook in n8n credentials.
- **Email:** Send Email node; configure an SMTP credential and intended recipient.
- **Generic webhook:** HTTP Request node with your URL and authentication credential.

Use the event's actual `metadata.symbol`, `buy_venue`, `sell_venue`, `gross_spread_percent`, `net_edge_percent`, `confidence_score`, and `liquidity_score`. Never manufacture market figures. No external message is sent by the default workflows.

## Failure behavior

- Bounded asynchronous queue (1000), no per-tick events.
- Three delivery attempts with backoff, then a database dead-letter record.
- Local notifications/events and the quant engine keep working when n8n is unavailable.
- Automation callbacks require a shared token and revalidate age, depth, profit, confidence, liquidity, capital, daily limits, and the current auto switch.
- The kill switch disarms memory immediately, even if persisting the configuration subsequently fails.
- State is single-process; do not scale the backend to multiple workers without distributed reservations.

## References

- [Official Docker installation](https://docs.n8n.io/hosting/installation/docker/)
- [Workflow import/export](https://docs.n8n.io/workflows/export-import/)
- [Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [HTTP Request node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/)
