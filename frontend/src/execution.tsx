import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Download,
  Pause,
  Play,
  Power,
  ShieldCheck,
  Square,
  X,
} from "lucide-react";
import { request, fmt, time, compact } from "./api";
import {
  BookPanel,
  InstrumentChart,
  PanelHead,
  Radar,
  Badge,
  Empty,
} from "./panels";
import type { Opportunity, Price, Snapshot } from "./types";
export type AutomationState = {
  n8n: string;
  last_success: number | null;
  delivery_failures: number;
  queued: number;
  dropped: number;
  config: {
    auto_paper_trade: boolean;
    high_confidence_alerts: boolean;
    min_auto_edge: number;
    min_auto_confidence: number;
    max_auto_capital: number;
    max_daily_paper_trades: number;
    min_liquidity: number;
  };
  events: {
    event_id: string;
    event_type: string;
    timestamp: number;
    symbol: string;
    source: string;
    venue: string;
    severity: string;
    metadata: Record<string, unknown>;
  }[];
};
export type PaperOrder = {
  order_id: string;
  symbol: string;
  venue: string;
  source: string;
  side: string;
  order_type: string;
  quantity: number;
  requested_price: number | null;
  average_fill_price: number;
  filled_quantity: number;
  remaining_quantity: number;
  fees: number;
  slippage: number;
  status: string;
  created_at: number;
  latency_ms: number;
  reason: string;
  history: { timestamp: number; status: string; reason: string }[];
};
export type Position = {
  symbol: string;
  venue: string;
  source: string;
  quantity: number;
  average_entry: number;
  mark_price: number;
  market_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  stale: boolean;
};
export type ExecutionState = {
  orders: PaperOrder[];
  account: {
    available_cash: number;
    reserved_cash: number;
    portfolio_value: number;
    exposure: number;
    unrealized_pnl: number;
    realized_pnl: number;
    fees: number;
    net_pnl: number;
    drawdown_percent: number;
    positions: Position[];
  };
  assumptions: string[];
};
export type ExtendedSnapshot = Snapshot & {
  automation: AutomationState;
  execution: ExecutionState;
  replay: {
    enabled: boolean;
    playing: boolean;
    speed: number;
    index: number;
    total: number;
  };
  system: {
    uptime_seconds: number;
    events_per_second: number;
    errors: number;
    detected: number;
    expired: number;
  };
};
const millis = (n: number) => `${time(n)}.${String(n % 1000).padStart(3, "0")}`;

export function TradingTerminal({
  data,
  price,
  onPrice,
  onOpportunity,
}: {
  data: ExtendedSnapshot;
  price: Price | undefined;
  onPrice: (p: Price) => void;
  onOpportunity: (o: Opportunity) => void;
}) {
  const [side, setSide] = useState("BUY"),
    [orderType, setOrderType] = useState("MARKET"),
    [quantity, setQuantity] = useState("0.01"),
    [limit, setLimit] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [tab, setTab] = useState("Orders");
  const account = data.execution?.account;
  const unique = data.prices.filter(
    (p, i, all) =>
      p.quote === "USDT" && all.findIndex((x) => x.symbol === p.symbol) === i,
  );
  async function submit() {
    if (!price) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const order = await request<PaperOrder>("/orders", {
        method: "POST",
        body: JSON.stringify({
          symbol: price.symbol,
          venue: price.exchange,
          side,
          order_type: orderType,
          quantity: Number(quantity),
          requested_price: orderType === "LIMIT" ? Number(limit) : null,
          idempotency_key: crypto.randomUUID(),
        }),
      });
      if (order.status === "REJECTED") setError(order.reason);
      else
        setMessage(
          `${order.side} ${order.symbol} · ${order.status} · simulated`,
        );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function cancel(id: string) {
    try {
      await request(`/orders/${id}/cancel`, { method: "POST" });
      setMessage("Paper order cancelled. Reservation released.");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="notice">
        <span className="gold">PAPER EXECUTION ONLY</span>
        <span>
          Long-only · marketable limit fills · no exchange queue priority
        </span>
      </div>
      <div className="instrument-controls">
        <select
          aria-label="Trading instrument"
          value={price?.symbol}
          onChange={(e) => {
            const p = unique.find((p) => p.symbol === e.target.value);
            if (p) onPrice(p);
          }}
        >
          {unique.map((p) => (
            <option key={p.symbol}>{p.symbol}</option>
          ))}
        </select>
        <select
          aria-label="Trading venue"
          value={price?.exchange}
          onChange={(e) => {
            const p = data.prices.find(
              (p) =>
                p.symbol === price?.symbol && p.exchange === e.target.value,
            );
            if (p) onPrice(p);
          }}
        >
          {data.prices
            .filter((p) => p.symbol === price?.symbol)
            .map((p) => (
              <option key={p.exchange}>{p.exchange}</option>
            ))}
        </select>
        {price && <Badge source={price.source} stale={price.stale} />}
      </div>
      {account && (
        <div className="kpi-grid">
          <div>
            <span>PORTFOLIO VALUE · USDT</span>
            <strong>{fmt(account.portfolio_value)}</strong>
            <small>Exposure {fmt(account.exposure)}</small>
          </div>
          <div>
            <span>AVAILABLE CASH</span>
            <strong>{fmt(account.available_cash)}</strong>
            <small>Reserved {fmt(account.reserved_cash)}</small>
          </div>
          <div>
            <span>UNREALIZED P&L</span>
            <strong
              className={account.unrealized_pnl >= 0 ? "positive" : "negative"}
            >
              {fmt(account.unrealized_pnl)}
            </strong>
            <small>Marked at current bid</small>
          </div>
          <div>
            <span>REALIZED P&L</span>
            <strong
              className={account.realized_pnl >= 0 ? "positive" : "negative"}
            >
              {fmt(account.realized_pnl)}
            </strong>
            <small>Drawdown {fmt(account.drawdown_percent)}%</small>
          </div>
        </div>
      )}
      <div className="trading-grid">
        <InstrumentChart price={price} small />
        <section className="panel order-ticket">
          <PanelHead
            title="Paper order ticket"
            sub="All orders are simulated"
            action={<ShieldCheck size={15} className="gold" />}
          />
          <div className="ticket-body">
            <div className="ticket-side">
              {["BUY", "SELL"].map((s) => (
                <button
                  key={s}
                  className={
                    side === s
                      ? s === "BUY"
                        ? "selected-buy"
                        : "selected-sell"
                      : ""
                  }
                  onClick={() => setSide(s)}
                >
                  PAPER {s}
                </button>
              ))}
            </div>
            <div className="tabs">
              {["MARKET", "LIMIT"].map((t) => (
                <button
                  key={t}
                  className={orderType === t ? "active" : ""}
                  onClick={() => setOrderType(t)}
                >
                  {t}
                </button>
              ))}
            </div>
            <label>
              Quantity <span>{price?.base}</span>
              <input
                aria-label="Order quantity"
                type="number"
                min="0.00000001"
                step="0.01"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </label>
            {orderType === "LIMIT" && (
              <label>
                Limit price <span>{price?.quote}</span>
                <input
                  aria-label="Limit price"
                  type="number"
                  min="0.00000001"
                  step=".01"
                  placeholder={String(price?.price || "")}
                  value={limit}
                  onChange={(e) => setLimit(e.target.value)}
                />
              </label>
            )}
            <div className="setting-row">
              <span>Estimated notional</span>
              <b>
                {fmt(
                  Number(quantity) *
                    (orderType === "LIMIT" ? Number(limit) : price?.price || 0),
                )}{" "}
                {price?.quote}
              </b>
            </div>
            <p className="muted">
              Market orders walk current depth. Limit orders remain open until
              marketable. Selling requires owned inventory at this venue.
            </p>
            {error && <p className="error">{error}</p>}
            {message && <p className="success">{message}</p>}
            <button
              className={`execute ${side === "SELL" ? "sell-button" : ""}`}
              disabled={busy || !price || price.stale || Number(quantity) <= 0}
              onClick={submit}
            >
              {busy ? "Submitting simulation…" : `Paper ${side.toLowerCase()}`}{" "}
              <ArrowRight size={15} />
            </button>
          </div>
        </section>
        <BookPanel price={price} />
        <Radar
          ops={data.opportunities
            .filter((o) => o.symbol === price?.symbol)
            .slice(0, 5)}
          onSelect={onOpportunity}
          onAll={() => {
            location.hash = "Arbitrage";
          }}
        />
      </div>
      <section className="panel">
        <div className="filter-bar">
          <div className="tabs">
            {["Orders", "Positions", "Activity"].map((t) => (
              <button
                className={tab === t ? "active" : ""}
                key={t}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          <span className="muted">Updates via market WebSocket</span>
        </div>
        {tab === "Orders" && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "TIME",
                    "SYMBOL / VENUE",
                    "SIDE / TYPE",
                    "QUANTITY",
                    "FILLED",
                    "AVG FILL",
                    "FEES",
                    "STATUS",
                    "ACTION",
                  ].map((t) => (
                    <th key={t}>{t}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.execution?.orders.map((o) => (
                  <tr key={o.order_id}>
                    <td className="mono">{millis(o.created_at)}</td>
                    <td>
                      <b>{o.symbol}</b>
                      <small>
                        {o.venue} · {(o.source === "demo" ? "SIMULATED" : o.source.toUpperCase())}
                      </small>
                    </td>
                    <td className={o.side === "BUY" ? "positive" : "negative"}>
                      {o.side}
                      <small>{o.order_type}</small>
                    </td>
                    <td>{fmt(o.quantity, 6)}</td>
                    <td>{fmt(o.filled_quantity, 6)}</td>
                    <td>
                      {o.average_fill_price
                        ? fmt(o.average_fill_price, 4)
                        : "—"}
                    </td>
                    <td>{fmt(o.fees, 4)}</td>
                    <td>
                      <span
                        className={`badge ${o.status === "FILLED" ? "positive" : o.status === "REJECTED" ? "negative" : "gold"}`}
                      >
                        {o.status}
                      </span>
                      <small>{o.reason}</small>
                    </td>
                    <td>
                      {["OPEN", "PARTIALLY_FILLED", "SUBMITTED"].includes(
                        o.status,
                      ) && (
                        <button
                          className="secondary-button"
                          onClick={() => cancel(o.order_id)}
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.execution?.orders.length && (
              <Empty
                title="No paper orders yet"
                detail="Use the order ticket to submit a simulated market or limit order."
              />
            )}
          </div>
        )}
        {tab === "Positions" && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "SYMBOL",
                    "VENUE",
                    "QUANTITY",
                    "AVG ENTRY",
                    "MARK",
                    "VALUE",
                    "UNREALIZED",
                    "REALIZED",
                    "STATUS",
                  ].map((t) => (
                    <th key={t}>{t}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {account?.positions.map((p) => (
                  <tr key={`${p.venue}:${p.symbol}:${p.source}`}>
                    <td>{p.symbol}</td>
                    <td>{p.venue}</td>
                    <td>{fmt(p.quantity, 6)}</td>
                    <td>{fmt(p.average_entry, 4)}</td>
                    <td>{fmt(p.mark_price, 4)}</td>
                    <td>{fmt(p.market_value)}</td>
                    <td
                      className={
                        p.unrealized_pnl >= 0 ? "positive" : "negative"
                      }
                    >
                      {fmt(p.unrealized_pnl, 4)}
                    </td>
                    <td>{fmt(p.realized_pnl, 4)}</td>
                    <td>
                      <Badge source={p.source} stale={p.stale} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!account?.positions.length && (
              <Empty
                title="No open positions"
                detail="Paper fills and partial arbitrage exposure will appear here."
              />
            )}
          </div>
        )}
        {tab === "Activity" && (
          <EventLog
            events={data.automation.events.filter((e) =>
              /ORDER|TRADE|ARBITRAGE/.test(e.event_type),
            )}
          />
        )}
      </section>
    </>
  );
}
export function EventLog({ events }: { events: AutomationState["events"] }) {
  return (
    <div className="event-log">
      {events.slice(0, 50).map((e) => (
        <div className="alert-row" key={e.event_id}>
          <time>{millis(e.timestamp)}</time>
          <span>
            <b>{e.event_type.replaceAll("_", " ")}</b>
            <small>
              {e.symbol} {e.venue} {String(e.metadata.reason || "")}
            </small>
          </span>
          <span className="muted">{e.source}</span>
        </div>
      ))}
    </div>
  );
}
export function AutomationCenter({ data }: { data: ExtendedSnapshot }) {
  const [config, setConfig] = useState<AutomationState["config"] | null>(null),
    [busy, setBusy] = useState(false),
    [msg, setMsg] = useState("");
  useEffect(() => {
    if (!config && data.automation) setConfig(data.automation.config);
  }, [data.automation, config]);
  async function save() {
    if (!config) return;
    setBusy(true);
    try {
      await request("/automation/config", {
        method: "PUT",
        body: JSON.stringify(config),
      });
      setMsg("Automation settings saved. Execution is always simulated.");
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function kill() {
    try {
      const result = await request<AutomationState>("/automation/kill", {
        method: "POST",
      });
      setConfig(result.config);
      setMsg("Auto paper trading stopped immediately.");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }
  return (
    <>
      <div className="automation-summary">
        <div>
          <span className="eyebrow">EVENT-DRIVEN ORCHESTRATION</span>
          <h2>Automation, with guardrails.</h2>
          <p>
            Python calculates. n8n orchestrates. Every execution is simulated.
          </p>
        </div>
        <button className="kill-button" onClick={kill}>
          <Square size={13} /> Stop auto paper trading
        </button>
      </div>
      <div className="three-grid">
        <section className="panel">
          <PanelHead
            title="n8n Community Edition"
            sub="Self-hosted · no cloud subscription"
          />
          <div className="automation-card">
            <span
              className={`large-status ${data.automation.n8n === "connected" ? "positive" : "gold"}`}
            >
              <i className="dot" />
              {data.automation.n8n.toUpperCase()}
            </span>
            <p>
              Selected lifecycle events only. The quant engine continues when
              n8n is unavailable.
            </p>
            <div className="setting-row">
              <span>Queued events</span>
              <b>{data.automation.queued}</b>
            </div>
            <div className="setting-row">
              <span>Delivery failures</span>
              <b>{data.automation.delivery_failures}</b>
            </div>
            <a
              className="secondary-button"
              href="http://localhost:5678"
              target="_blank"
              rel="noreferrer"
            >
              Open local n8n <ArrowRight size={12} />
            </a>
          </div>
        </section>
        <section className="panel">
          <PanelHead
            title="Paper automation"
            sub="Revalidated by Python before every fill"
            action={
              <span
                className={`badge ${data.automation.config.auto_paper_trade ? "positive" : "gold"}`}
              >
                {data.automation.config.auto_paper_trade ? "ON" : "OFF"}
              </span>
            }
          />
          {config && (
            <div className="automation-card">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={config.auto_paper_trade}
                  onChange={(e) =>
                    setConfig({ ...config, auto_paper_trade: e.target.checked })
                  }
                />{" "}
                Enable auto paper arbitrage
              </label>
              {(
                [
                  "min_auto_edge",
                  "min_auto_confidence",
                  "max_auto_capital",
                  "max_daily_paper_trades",
                  "min_liquidity",
                ] as const
              ).map((k) => (
                <label className="automation-field" key={k}>
                  <span>{k.replaceAll("_", " ")}</span>
                  <input
                    type="number"
                    min="0"
                    step={k === "min_auto_edge" ? ".01" : "1"}
                    value={config[k]}
                    onChange={(e) =>
                      setConfig({ ...config, [k]: +e.target.value })
                    }
                  />
                </label>
              ))}
              <button
                className="secondary-button"
                disabled={busy}
                onClick={save}
              >
                {busy ? "Saving…" : "Save automation settings"}
              </button>
            </div>
          )}
        </section>
        <section className="panel">
          <PanelHead
            title="Notifications & workflows"
            sub="Local notifications work without credentials"
          />
          <div className="automation-card">
            <div className="setting-row">
              <span>Local terminal</span>
              <b className="positive">ENABLED</b>
            </div>
            <div className="setting-row">
              <span>Feed health monitor</span>
              <b className="positive">ENGINE ON</b>
            </div>
            <div className="setting-row">
              <span>Scheduled reports</span>
              <b className="gold">n8n WORKFLOW</b>
            </div>
            {["Telegram", "Discord", "Email", "Generic webhook"].map((n) => (
              <div className="setting-row" key={n}>
                <span>{n}</span>
                <b>OPTIONAL</b>
              </div>
            ))}
            <p>
              Import the workflows in automation/workflows. Configure external
              credentials inside your local n8n instance; secrets never enter
              the browser.
            </p>
          </div>
        </section>
      </div>
      {msg && <p className="notice">{msg}</p>}
      <section className="panel">
        <PanelHead
          title="Automation audit log"
          sub="Lifecycle transitions · delivery · paper execution · milliseconds"
        />
        <EventLog events={data.automation.events} />
      </section>
    </>
  );
}
export function SystemMonitor({
  data,
  connected,
}: {
  data: ExtendedSnapshot;
  connected: boolean;
}) {
  const [reports, setReports] = useState<Record<string, unknown>[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    request<Record<string, unknown>[]>("/reports")
      .then(setReports)
      .catch((e) => setError(e.message));
  }, []);
  async function report() {
    try {
      const r = await request<Record<string, unknown>>("/reports", {
        method: "POST",
      });
      setReports((rs) => [r, ...rs]);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="kpi-grid">
        <div>
          <span>SYSTEM UPTIME</span>
          <strong>
            {fmt(data.system.uptime_seconds / 60, 1)}
            <em>min</em>
          </strong>
          <small>Current backend process</small>
        </div>
        <div>
          <span>EVENTS / SECOND</span>
          <strong>{data.system.events_per_second}</strong>
          <small>Lifecycle events, not market ticks</small>
        </div>
        <div>
          <span>DETECTION</span>
          <strong>
            {fmt(data.detection_ms, 2)}
            <em>ms</em>
          </strong>
          <small>Loop compute {fmt(data.end_to_end_ms, 1)} ms</small>
        </div>
        <div>
          <span>OPPORTUNITIES OBSERVED</span>
          <strong>{data.system.detected}</strong>
          <small>{data.system.expired} expired</small>
        </div>
      </div>
      <section className="panel">
        <PanelHead
          title="Infrastructure"
          sub="Actual service health · local fallback states are explicit"
        />
        <div className="infra-grid">
          {Object.entries({
            Backend: "ONLINE",
            Database: data.database,
            Redis: data.redis,
            n8n: data.automation.n8n,
            WebSocket: connected ? "CONNECTED" : "DISCONNECTED",
          }).map(([name, status]) => (
            <div key={name}>
              <span>{name}</span>
              <b
                className={
                  /ONLINE|CONNECTED|connected/.test(status) &&
                  !status.includes("disconnected")
                    ? "positive"
                    : "gold"
                }
              >
                {status}
              </b>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <PanelHead
          title="Provider health"
          sub="Stale books are excluded from detection"
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {["PROVIDER", "STATE", "DATA SOURCE", "LATENCY", "DETAIL"].map(
                  (t) => (
                    <th key={t}>{t}</th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.venues).map(([name, v]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{v.state.toUpperCase()}</td>
                  <td>{(v.source === "demo" ? "SIMULATED" : v.source.toUpperCase())}</td>
                  <td>{v.latency_ms ? fmt(v.latency_ms, 1) + " ms" : "—"}</td>
                  <td>{v.error || "No provider error reported"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <Reports reports={reports} onGenerate={report} error={error} />
    </>
  );
}
export function Reports({
  reports,
  onGenerate,
  error,
}: {
  reports: Record<string, unknown>[];
  onGenerate: () => void;
  error: string;
}) {
  return (
    <section className="panel">
      <PanelHead
        title="Session reports"
        sub="Saved to the database · also callable from the scheduled n8n workflow"
        action={
          <button className="secondary-button" onClick={onGenerate}>
            Generate report
          </button>
        }
      />
      {error && <p className="error">{error}</p>}
      {reports.length ? (
        reports.map((r) => (
          <details className="report-item" key={String(r.id)}>
            <summary>
              {new Date(Number(r.timestamp)).toLocaleString("en-GB", {
                timeZone: "Asia/Kolkata",
                hour12: false,
              }) + " IST"}{" "}
              <span>
                {String(r.markets_monitored)} books · {String(r.paper_trades)}{" "}
                paper trades
              </span>
            </summary>
            <pre>{JSON.stringify(r, null, 2)}</pre>
          </details>
        ))
      ) : (
        <Empty
          title="No reports yet"
          detail="Generate a session report here, or enable the n8n schedule to collect reports automatically."
        />
      )}
    </section>
  );
}
export function ReplayControls({ data }: { data: ExtendedSnapshot }) {
  const [error, setError] = useState(""),
    [speed, setSpeed] = useState(1);
  async function load(file: File) {
    try {
      const contents = JSON.parse(await file.text());
      await request("/replay/load", {
        method: "POST",
        body: JSON.stringify({
          frames: Array.isArray(contents) ? contents : contents.frames,
        }),
      });
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function control(action: string) {
    try {
      await request("/replay/control", {
        method: "POST",
        body: JSON.stringify({ action, speed }),
      });
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <section className="panel">
      <PanelHead
        title="Market replay"
        sub="Recorded depth frames · historical intervals preserved at selected speed"
        action={
          <span className="badge gold">
            {data.replay.enabled ? "REPLAY" : "SESSION DATA"}
          </span>
        }
      />
      <div className="replay-controls">
        <label className="secondary-button">
          Load recorded JSON
          <input
            type="file"
            accept=".json"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) load(f);
            }}
          />
        </label>
        <button className="secondary-button" onClick={() => control("play")}>
          <Play size={13} />
          Play
        </button>
        <button className="secondary-button" onClick={() => control("pause")}>
          <Pause size={13} />
          Pause
        </button>
        <select
          aria-label="Replay speed"
          value={speed}
          onChange={(e) => setSpeed(+e.target.value)}
        >
          {[1, 2, 5, 10].map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
        <button className="secondary-button" onClick={() => control("stop")}>
          <Square size={12} />
          Return to market
        </button>
        <span className="muted">
          Frame {data.replay.index} / {data.replay.total}
        </span>
      </div>
      <p className="replay-note">
        No fabricated history. Replay preserves original quote age, labels all
        quotes REPLAY, and runs the same risk engine. Paused books become stale
        normally.
      </p>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
