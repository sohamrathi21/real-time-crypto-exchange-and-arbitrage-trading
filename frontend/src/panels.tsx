import { TradeReview } from "./trade-review";
import { useEffect, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  ChevronRight,
  X,
  Check,
  AlertTriangle,
} from "lucide-react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { request, fmt, compact, time, API } from "./api";
import { StreamChart } from "./charts";
import type { Book, Opportunity, Price, Snapshot } from "./types";
export const names: Record<string, string> = {
  BTC: "Bitcoin",
  ETH: "Ethereum",
  SOL: "Solana",
  AAPL: "Apple Inc.",
  MSFT: "Microsoft",
  NVDA: "NVIDIA",
  AVAX: "Avalanche",
  LINK: "Chainlink",
  XRP: "XRP",
  DOGE: "Dogecoin",
  ADA: "Cardano",
  DOT: "Polkadot",
  LTC: "Litecoin",
  INJ: "Injective",
  SUI: "Sui",
};
export const label = (type: string) => type.replaceAll("_", " ");
export function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty">
      <span className="empty-icon">◇</span>
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}
export function PanelHead({
  title,
  sub,
  action,
}: {
  title: string;
  sub?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="panel-head">
      <div>
        <h3>{title}</h3>
        {sub && <span>{sub}</span>}
      </div>
      {action}
    </div>
  );
}
export function Badge({
  source,
  stale = false,
}: {
  source: string;
  stale?: boolean;
}) {
  return (
    <span
      className={`badge ${stale ? "negative" : source === "demo" ? "gold" : "positive"}`}
    >
      {stale
        ? "STALE"
        : source === "demo"
          ? "SIMULATED"
          : source === "replay"
            ? "REPLAY"
            : source === "unavailable"
              ? "N/A"
              : "LIVE"}
    </span>
  );
}
export function Score({ value }: { value: number }) {
  return (
    <span className="score">
      <span className="score-track">
        <i style={{ width: `${value}%` }} />
      </span>
      <b>{Math.round(value)}</b>
    </span>
  );
}
export function Radar({
  ops,
  onSelect,
  onAll,
}: {
  ops: Opportunity[];
  onSelect: (o: Opportunity) => void;
  onAll: () => void;
}) {
  return (
    <section className="panel radar">
      <PanelHead
        title="Arbitrage radar"
        sub="Depth-verified · ranked by confidence"
        action={<span className="count">{ops.length}</span>}
      />
      {ops.length ? (
        ops.slice(0, 5).map((op) => (
          <button
            className="radar-row"
            key={op.id}
            onClick={() => onSelect(op)}
          >
            <div className="asset-dot">
              {op.type === "triangular" ? "△" : op.symbol.slice(0, 1)}
            </div>
            <div className="radar-name">
              <strong>{op.symbol}</strong>
              <small>
                {op.buy_venue} <span>→</span> {op.sell_venue}
              </small>
            </div>
            <div className="right">
              <b className="positive mono">+{fmt(op.net_edge_percent, 3)}%</b>
              <small>
                CONF {op.confidence_score.toFixed(0)}{" "}
                <span className="gold">· {(op.source === "demo" ? "SIMULATED" : op.source.toUpperCase())}</span>
              </small>
            </div>
          </button>
        ))
      ) : (
        <Empty
          title="Scanning for an edge"
          detail="Only profitable routes passing all risk checks appear here."
        />
      )}
      <button className="panel-link" onClick={onAll}>
        Open arbitrage intelligence <ChevronRight size={14} />
      </button>
    </section>
  );
}

export function InstrumentChart({
  price,
  small = false,
}: {
  price: Price | undefined;
  small?: boolean;
}) {
  const [points, setPoints] = useState<{ timestamp: number; price: number }[]>(
      [],
    ),
    [chartType, setChartType] = useState("Line"),
    [interval, setIntervalValue] = useState(1),
    [error, setError] = useState("");
  useEffect(() => {
    setPoints([]);
    if (!price) return;
    let active = true;
    const load = () =>
      request<{ timestamp: number; price: number }[]>(
        `/history/${encodeURIComponent(price.exchange)}/${price.symbol}`,
      )
        .then((p) => {
          if (active) {
            setPoints(p);
            setError("");
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    load();
    const timer = setInterval(load, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [price?.symbol, price?.exchange]);
  if (!price)
    return (
      <section className="panel">
        <Empty
          title="Waiting for market data"
          detail="The selected provider has not delivered a quote."
        />
      </section>
    );
  const first = points[0]?.price || price.price,
    change = (price.price / first - 1) * 100;
  const visible = points.filter(
    (p) => p.timestamp >= Date.now() - interval * 60000,
  );
  const candles = Object.values(
    visible.reduce<
      Record<
        number,
        {
          timestamp: number;
          open: number;
          high: number;
          low: number;
          close: number;
        }
      >
    >((acc, p) => {
      const key = Math.floor(p.timestamp / 10000) * 10000;
      const c = acc[key];
      if (c) {
        c.high = Math.max(c.high, p.price);
        c.low = Math.min(c.low, p.price);
        c.close = p.price;
      } else
        acc[key] = {
          timestamp: key,
          open: p.price,
          high: p.price,
          low: p.price,
          close: p.price,
        };
      return acc;
    }, {}),
  );
  const low = Math.min(...visible.map((p) => p.price), price.price) * 0.99995,
    high = Math.max(...visible.map((p) => p.price), price.price) * 1.00005;
  const y = (p: number) => 185 - ((p - low) / (high - low)) * 160;
  return (
    <section className="panel instrument-chart">
      <PanelHead
        title={`${price.symbol}  /  ${names[price.base] || price.base}`}
        sub={`${price.exchange} · ${price.asset_class === "crypto" ? "Spot market" : "Simulated equity venue"} · quote ${price.quote}`}
        action={<Badge source={price.source} stale={price.stale} />}
      />
      <div className="chart-summary">
        <div>
          <span className="hero-price">
            {fmt(price.price, price.price < 1 ? 4 : 2)}
          </span>
          <span className={change >= 0 ? "positive" : "negative"}>
            {change >= 0 ? (
              <ArrowUpRight size={15} />
            ) : (
              <ArrowDownRight size={15} />
            )}{" "}
            {change >= 0 ? "+" : ""}
            {fmt(change, 3)}% <small>session</small>
          </span>
        </div>
        <div className="chart-quote">
          <span>
            BID <b>{fmt(price.bid)}</b>
          </span>
          <span>
            ASK <b>{fmt(price.ask)}</b>
          </span>
          <span>
            SPREAD <b>{fmt(price.spread_percent, 3)}%</b>
          </span>
        </div>
      </div>
      <div className="chart-toolbar">
        <div className="segmented">
          {[1, 5, 15, 60].map((v) => (
            <button
              key={v}
              onClick={() => setIntervalValue(v)}
              className={interval === v ? "active" : ""}
            >
              {v === 60 ? "1H" : `${v}m`}
            </button>
          ))}
        </div>
        <span className="muted">Collected session data</span>
        <div className="segmented">
          {["Line", "Candles"].map((t) => (
            <button
              key={t}
              className={chartType === t ? "active" : ""}
              onClick={() => setChartType(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      {error ? (
        <p className="error">{error}</p>
      ) : visible.length < 2 ? (
        <Empty
          title="Building the session chart"
          detail="Prices are recorded from incoming order books. Historical candles are not yet available."
        />
      ) : chartType === "Line" ? (
        <StreamChart
          data={visible}
          field="price"
          height={small ? 180 : 195}
          color="#71bda9"
        />
      ) : (
        <div className="candle-chart">
          <svg
            viewBox="0 0 800 210"
            role="img"
            aria-label="10 second candles derived from sampled mid prices"
          >
            {[30, 80, 130, 180].map((v) => (
              <line key={v} x1="0" x2="800" y1={v} y2={v} stroke="#242b31" />
            ))}
            {candles.map((c, i) => {
              const x = 20 + i * (740 / Math.max(candles.length, 1));
              const up = c.close >= c.open;
              return (
                <g
                  key={c.timestamp}
                  stroke={up ? "#71bda9" : "#cd7c81"}
                  fill={up ? "#71bda9" : "#cd7c81"}
                >
                  <line x1={x} x2={x} y1={y(c.high)} y2={y(c.low)} />
                  <rect
                    x={x - 3}
                    y={Math.min(y(c.open), y(c.close))}
                    width={6}
                    height={Math.max(1, Math.abs(y(c.open) - y(c.close)))}
                  />
                </g>
              );
            })}
          </svg>
          <small>
            10-second candles from sampled midquotes; not exchange trade OHLC.
          </small>
        </div>
      )}
      <div className="chart-foot">
        <span>
          SESSION OPEN <b>{fmt(first)}</b>
        </span>
        <span>
          HIGH{" "}
          <b>{fmt(Math.max(...points.map((p) => p.price), price.price))}</b>
        </span>
        <span>
          LOW <b>{fmt(Math.min(...points.map((p) => p.price), price.price))}</b>
        </span>
        <span>
          24H VOL <b title="Provider does not supply 24h volume">—</b>
        </span>
        <span>
          PREV CLOSE <b>—</b>
        </span>
      </div>
    </section>
  );
}

export function BookPanel({ price }: { price: Price | undefined }) {
  const [book, setBook] = useState<Book | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    setBook(null);
    if (!price) return;
    let active = true;
    let socket: WebSocket;
    let retry: ReturnType<typeof setTimeout>;
    const connect = () => {
      const base = import.meta.env.VITE_API_URL
        ? API.replace(/^http/, "ws")
        : `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`;
      socket = new WebSocket(
        `${base}/ws/orderbook/${encodeURIComponent(price.exchange)}/${price.symbol}`,
      );
      socket.onmessage = (e) => {
        try {
          const b = JSON.parse(e.data);
          if (b.bids) {
            setBook(b);
            setError("");
          } else setError(b.error || "Book unavailable");
        } catch {
          setError("Invalid book event");
        }
      };
      socket.onerror = () => setError("Order book stream reconnecting");
      socket.onclose = () => {
        if (active) retry = setTimeout(connect, 2000);
      };
    };
    connect();
    return () => {
      active = false;
      clearTimeout(retry);
      socket?.close();
    };
  }, [price?.symbol, price?.exchange]);
  if (!price || !book)
    return (
      <section className="panel">
        <Empty
          title={error || "Loading order book"}
          detail="Waiting for a valid depth snapshot."
        />
      </section>
    );
  let bid = 0,
    ask = 0;
  const depth = book.bids.map((b, i) => {
    bid += b.quantity * b.price;
    ask += (book.asks[i]?.quantity || 0) * (book.asks[i]?.price || 0);
    return { level: i + 1, bid, ask };
  });
  const bidTotal = book.bids.reduce((a, b) => a + b.quantity, 0),
    askTotal = book.asks.reduce((a, b) => a + b.quantity, 0);
  return (
    <section className="panel">
      <PanelHead
        title={`Order book · ${price.symbol}`}
        sub={`${price.exchange} · aggregated price levels`}
        action={<Badge source={price.source} stale={price.stale} />}
      />
      <div className="book-grid">
        <div>
          <div className="book-row muted">
            <span>PRICE ({price.quote})</span>
            <span>SIZE</span>
            <span>TOTAL</span>
          </div>
          {book.asks
            .slice(0, 7)
            .reverse()
            .map((l) => (
              <div className="book-row ask" key={l.price}>
                <span>{fmt(l.price, 4)}</span>
                <span>{fmt(l.quantity, 4)}</span>
                <span>{compact(l.price * l.quantity)}</span>
              </div>
            ))}
          <div className="book-spread">
            Spread <b>{fmt(book.asks[0].price - book.bids[0].price, 4)}</b>
            <span>{fmt(price.spread_percent, 3)}%</span>
          </div>
          {book.bids.slice(0, 7).map((l) => (
            <div className="book-row bid" key={l.price}>
              <span>{fmt(l.price, 4)}</span>
              <span>{fmt(l.quantity, 4)}</span>
              <span>{compact(l.price * l.quantity)}</span>
            </div>
          ))}
        </div>
        <div className="depth-panel">
          <h4>Cumulative depth by level</h4>
          <ResponsiveContainer width="100%" height={225}>
            <AreaChart data={depth}>
              <XAxis dataKey="level" stroke="#6d7781" fontSize={10} />
              <YAxis
                tickFormatter={compact}
                stroke="#6d7781"
                fontSize={10}
                width={50}
              />
              <Tooltip
                contentStyle={{
                  background: "#141a1f",
                  border: "1px solid #333",
                }}
              />
              <Area
                dataKey="bid"
                stroke="#71bda9"
                fill="#71bda9"
                fillOpacity={0.1}
              />
              <Area
                dataKey="ask"
                stroke="#cd7c81"
                fill="#cd7c81"
                fillOpacity={0.08}
              />
            </AreaChart>
          </ResponsiveContainer>
          <div className="detail-metrics">
            <span>
              Bid imbalance{" "}
              <b>{fmt((bidTotal / (bidTotal + askTotal)) * 100)}%</b>
            </span>
            <span>
              Displayed depth{" "}
              <b>
                {compact(bid + ask)} {price.quote}
              </b>
            </span>
            <span>
              Mid price{" "}
              <b>{fmt((book.asks[0].price + book.bids[0].price) / 2, 4)}</b>
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

export function OpportunityDetail({
  op,
  current,
  onClose,
  connected,
}: {
  op: Opportunity;
  current: boolean;
  onClose: () => void;
  connected: boolean;
}) {
  const [pending, setPending] = useState(false),
    [result, setResult] = useState(""),
    [error, setError] = useState(""),
    [scenario, setScenario] = useState("normal"),
    [execution, setExecution] = useState<{
      execution_legs: {
        side: string;
        status: string;
        vwap: number;
        quantity: number;
      }[];
      remaining_exposure: number;
      net_profit: number;
    } | null>(null);
  const [key] = useState(() => crypto.randomUUID());
  async function execute() {
    setPending(true);
    setError("");
    try {
      const trade = await request<NonNullable<typeof execution>>(
        "/paper-trades/execute",
        {
          method: "POST",
          body: JSON.stringify({
            opportunity_id: op.id,
            idempotency_key: key,
            execution_scenario: scenario,
          }),
        },
      );
      setExecution(trade);
      setResult("Paper execution recorded. Portfolio updated.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="overlay" onClick={onClose}>
      <aside
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Opportunity analysis"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-head">
          <span className="eyebrow">OPPORTUNITY ANALYSIS</span>
          <button aria-label="Close detail" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <h2>{op.symbol}</h2>
        <div className="flex gap-2 items-center">
          <span className="muted capitalize">{label(op.type)}</span>
          <Badge source={op.source} />
          {!current && <span className="negative">EXPIRED</span>}
        </div>
        <div className="route">
          <div>
            <small>BUY / START</small>
            <strong>{op.buy_venue}</strong>
            <b>{fmt(op.buy_price, 4)}</b>
          </div>
          <ChevronRight size={22} />
          <div>
            <small>SELL / FINISH</small>
            <strong>{op.sell_venue}</strong>
            <b>{fmt(op.sell_price, 4)}</b>
          </div>
        </div>
        {op.path.length > 0 && <p className="gold">{op.path.join(" → ")}</p>}
        <div className="profit-hero">
          <span>NET EDGE</span>
          <strong>
            +{fmt(op.net_edge_percent, 3)}
            <small>%</small>
          </strong>
          <p>
            Estimated profit{" "}
            <b>
              +{fmt(op.net_profit, 4)} {op.quote}
            </b>
          </p>
        </div>
        <TradeReview op={op} current={current} connected={connected} onClose={onClose} />
        <h4>
          Profitability breakdown <small>{op.quote}</small>
        </h4>
        <dl className="breakdown">
          <div>
            <dt>Gross profit · depth VWAP</dt>
            <dd>{fmt(op.gross_profit, 4)}</dd>
          </div>
          <div>
            <dt>Trading fees · all legs</dt>
            <dd className="negative">−{fmt(op.buy_fee + op.sell_fee, 4)}</dd>
          </div>
          <div>
            <dt>Residual slippage reserve</dt>
            <dd className="negative">−{fmt(op.estimated_slippage, 4)}</dd>
          </div>
          <div>
            <dt>Network + other costs</dt>
            <dd className="negative">
              −{fmt(op.network_cost + op.other_costs, 4)}
            </dd>
          </div>
          <div>
            <dt>Book impact · already in VWAP</dt>
            <dd>{fmt(op.price_impact, 4)}</dd>
          </div>
          <div className="total">
            <dt>Net profit</dt>
            <dd className="positive">+{fmt(op.net_profit, 4)}</dd>
          </div>
        </dl>
        <div className="detail-metrics">
          <span>
            Capital including reserve{" "}
            <b>
              {fmt(op.capital_required)} {op.quote}
            </b>
          </span>
          <span>
            {op.type === "triangular" ? "Starting amount" : "Trade quantity"}{" "}
            <b>{fmt(op.trade_quantity, 6)}</b>
          </span>
          <span>
            Latency estimate <b>{fmt(op.execution_latency, 0)} ms</b>
          </span>
          <span>
            Detected <b>{time(op.first_seen)}</b>
          </span>
          <span>
            Observed lifetime{" "}
            <b>{fmt((op.timestamp - op.first_seen) / 1000, 1)} s</b>
          </span>
        </div>
        <h4>
          Confidence{" "}
          <span className="gold">
            {op.confidence_score} / 100 ·{" "}
            {op.confidence_score >= 90
              ? "Exceptional"
              : op.confidence_score >= 75
                ? "Strong"
                : op.confidence_score >= 60
                  ? "Moderate"
                  : "Weak"}
          </span>
        </h4>
        <div className="factor-grid">
          {Object.entries(op.confidence_factors).map(([name, value]) => (
            <div key={name}>
              <span className="capitalize">{name}</span>
              <Score value={value} />
            </div>
          ))}
        </div>
        {op.legs.map((leg, i) => (
          <div className="leg" key={i}>
            <b>
              0{i + 1} · {leg.side.toUpperCase()} {leg.symbol}
            </b>
            <span>
              {fmt(leg.input, 6)} → {fmt(leg.output, 6)}
            </span>
            <small>
              Fee {fmt(leg.fee, 7)} {leg.fee_currency}
            </small>
          </div>
        ))}
        <h4>Execution assumptions</h4>
        <ul className="assumptions">
          {op.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
        {error && (
          <p className="error">
            <AlertTriangle size={15} />
            {error}
          </p>
        )}
        {result && (
          <p className="success">
            <Check size={15} />
            {result}
          </p>
        )}
        {op.source === "demo" && !result && (
          <label className="scenario-select">
            Simulation execution scenario
            <select
              aria-label="Execution scenario"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            >
              <option value="normal">Normal · current depth</option>
              {op.type !== "triangular" && (
                <option value="partial_sell">Leg risk · 60% sell fill</option>
              )}
              <option value="price_moved">Adverse move · reject</option>
            </select>
          </label>
        )}
        {execution && (
          <div className="execution-result">
            {execution.execution_legs.map((leg, i) => (
              <div key={i}>
                <b>
                  {leg.side} · {leg.status}
                </b>
                <span>
                  {fmt(leg.quantity, 6)} @ {fmt(leg.vwap, 4)}
                </span>
              </div>
            ))}
            <p className="positive">
              Realized simulated P&L: {fmt(execution.net_profit, 4)} {op.quote}
            </p>
            {execution.remaining_exposure > 0 && (
              <p className="gold">
                Open exposure: {fmt(execution.remaining_exposure, 6)}. Manage in
                Trading → Positions.
              </p>
            )}
          </div>
        )}
        <button
          className="execute"
          disabled={pending || !current || !connected || !!result}
          onClick={execute}
        >
          {pending
            ? "Validating latest books…"
            : result
              ? "Simulation recorded"
              : !current
                ? "Opportunity expired"
                : "Paper execute"}{" "}
          <ChevronRight size={16} />
        </button>
        <p className="muted center">
          Simulation only. No real orders are submitted.
        </p>
      </aside>
    </div>
  );
}
