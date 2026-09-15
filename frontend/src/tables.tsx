import { LiveArbitrage } from "./live-arbitrage";
import { IndianStocks } from "./india";
import { useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  Star,
  Trash2,
  SlidersHorizontal,
} from "lucide-react";
import { fmt, compact, time, request } from "./api";
import { Empty, PanelHead, Badge, Score, names, label } from "./panels";
import { StreamChart, Bars } from "./charts";
import type { Opportunity, Price, Snapshot } from "./types";

export function MarketTable({
  data,
  mode,
  onOpen,
  watch,
  onWatch,
  onReorder,
}: {
  data: Snapshot;
  mode: string;
  onOpen: (p: Price) => void;
  watch: string[];
  onWatch: (s: string) => void;
  onReorder: (s: string, d: number) => void;
}) {
  const [tab, setTab] = useState(mode === "Stocks" ? "India stocks" : "All"),
    [venue, setVenue] = useState("All venues"),
    [sort, setSort] = useState("symbol"),
    [query, setQuery] = useState(""),
    [minPrice, setMinPrice] = useState(0),
    [maxPrice, setMaxPrice] = useState(1000000),
    [minEdge, setMinEdge] = useState(0),
    [minConfidence, setMinConfidence] = useState(0),
    [minDepth, setMinDepth] = useState(0),
    [minSpread, setMinSpread] = useState(0);
  const lookup = new Map<string, Opportunity>();
  data.opportunities.forEach((o) => {
    const prior = lookup.get(o.symbol);
    if (!prior || prior.net_edge_percent < o.net_edge_percent)
      lookup.set(o.symbol, o);
  });
  const rows = useMemo(() => {
    let prices = data.prices.filter(
      (p) =>
        p.quote !== "BTC" && (venue === "All venues" || p.exchange === venue),
    );
    prices = prices.filter(
      (p, i, all) => all.findIndex((x) => x.symbol === p.symbol) === i,
    );
    if (mode === "Crypto" || tab === "Crypto")
      prices = prices.filter((p) => p.asset_class === "crypto");
    if (mode === "Stocks" || tab === "US stocks")
      prices = prices.filter((p) => p.asset_class === "equity");
    if (tab === "India stocks" || tab === "Indices") prices = [];
    if (mode === "Watchlist")
      prices = prices.filter((p) => watch.includes(p.symbol));
    prices = prices.filter(
      (p) =>
        `${p.symbol} ${names[p.base] || ""}`
          .toLowerCase()
          .includes(query.toLowerCase()) &&
        p.price >= minPrice &&
        p.price <= maxPrice &&
        p.depth_notional >= minDepth &&
        p.spread_percent >= minSpread &&
        (!minEdge ||
          (lookup.get(p.symbol)?.net_edge_percent || 0) >= minEdge) &&
        (!minConfidence ||
          (lookup.get(p.symbol)?.confidence_score || 0) >= minConfidence),
    );
    return prices.sort((a, b) =>
      mode === "Watchlist"
        ? watch.indexOf(a.symbol) - watch.indexOf(b.symbol)
        : sort === "price"
          ? b.price - a.price
          : sort === "depth"
            ? b.depth_notional - a.depth_notional
            : sort === "spread"
              ? b.spread_percent - a.spread_percent
              : sort === "edge"
                ? (lookup.get(b.symbol)?.net_edge_percent || 0) -
                  (lookup.get(a.symbol)?.net_edge_percent || 0)
                : a.symbol.localeCompare(b.symbol),
    );
  }, [
    data.prices,
    data.opportunities,
    mode,
    tab,
    venue,
    sort,
    query,
    minPrice,
    maxPrice,
    minEdge,
    minConfidence,
    minDepth,
    minSpread,
    watch,
  ]);
  if (tab === "India stocks") return <><div className="tabs"><button className="active" onClick={() => setTab("India stocks")}>India stocks</button><button onClick={() => setTab("US stocks")}>US stocks</button><button onClick={() => setTab("All")}>All markets</button></div><IndianStocks /></>;
  return (
    <section className="panel">
      <PanelHead
        title={
          mode === "Market Scanner"
            ? "Market scanner"
            : mode === "Watchlist"
              ? "Your watchlist"
              : "Market overview"
        }
        sub={`${rows.length} instruments · displayed quote venue · 24h statistics unavailable without a history feed`}
      />
      <div className="filter-bar">
        <div className="tabs">
          {(mode === "Stocks"
            ? ["US stocks", "India stocks"]
            : mode === "Crypto"
              ? ["Crypto"]
              : ["All", "Crypto", "US stocks", "India stocks", "Indices"]
          ).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={tab === t ? "active" : ""}
            >
              {t}
            </button>
          ))}
        </div>
        <input
          aria-label="Filter markets"
          placeholder="Filter symbols…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          aria-label="Exchange filter"
          value={venue}
          onChange={(e) => setVenue(e.target.value)}
        >
          {["All venues", ...Object.keys(data.venues)].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
        <select
          aria-label="Sort markets"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="symbol">Symbol</option>
          <option value="price">Highest price</option>
          <option value="depth">Highest book liquidity</option>
          <option value="spread">Widest spread</option>
          <option value="edge">Best net edge</option>
        </select>
      </div>
      {mode === "Market Scanner" && (
        <div className="filter-bar scanner-filters">
          <label>
            Min price
            <input
              type="number"
              min="0"
              value={minPrice}
              onChange={(e) => setMinPrice(+e.target.value)}
            />
          </label>
          <label>
            Max price
            <input
              type="number"
              min="0"
              value={maxPrice}
              onChange={(e) => setMaxPrice(+e.target.value)}
            />
          </label>
          <label>
            Min edge %
            <input
              type="number"
              step=".01"
              min="0"
              value={minEdge}
              onChange={(e) => setMinEdge(+e.target.value)}
            />
          </label>
          <label>
            Min confidence
            <input
              type="number"
              min="0"
              max="100"
              value={minConfidence}
              onChange={(e) => setMinConfidence(+e.target.value)}
            />
          </label>
          <label>
            Min book liquidity
            <input
              type="number"
              min="0"
              value={minDepth}
              onChange={(e) => setMinDepth(+e.target.value)}
            />
          </label>
          <label>
            Min spread %
            <input
              type="number"
              min="0"
              step=".01"
              value={minSpread}
              onChange={(e) => setMinSpread(+e.target.value)}
            />
          </label>
        </div>
      )}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th></th>
              <th>INSTRUMENT</th>
              <th>PRICE</th>
              <th>24H %</th>
              <th>BID</th>
              <th>ASK</th>
              <th>SPREAD</th>
              <th>BOOK LIQUIDITY</th>
              <th>VENUE</th>
              <th>NET EDGE</th>
              <th>STATUS</th>
              {mode === "Watchlist" && <th>ORDER</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.symbol}>
                <td>
                  <button
                    className={`icon-button ${watch.includes(p.symbol) ? "gold" : ""}`}
                    aria-label={`${watch.includes(p.symbol) ? "Remove" : "Add"} ${p.symbol} ${watch.includes(p.symbol) ? "from" : "to"} watchlist`}
                    onClick={() => onWatch(p.symbol)}
                  >
                    <Star
                      size={13}
                      fill={watch.includes(p.symbol) ? "currentColor" : "none"}
                    />
                  </button>
                </td>
                <td>
                  <button className="asset-link" onClick={() => onOpen(p)}>
                    <b>{p.symbol}</b>
                    <small>{names[p.base] || p.base}</small>
                  </button>
                </td>
                <td className="mono">{fmt(p.price, p.price < 1 ? 4 : 2)}</td>
                <td className="muted">—</td>
                <td className="mono">{fmt(p.bid, p.bid < 1 ? 4 : 2)}</td>
                <td className="mono">{fmt(p.ask, p.ask < 1 ? 4 : 2)}</td>
                <td className="mono">{fmt(p.spread_percent, 3)}%</td>
                <td className="mono">
                  {compact(p.depth_notional)} {p.quote}
                </td>
                <td>{p.exchange}</td>
                <td className="positive mono">
                  {lookup.has(p.symbol)
                    ? `+${fmt(lookup.get(p.symbol)!.net_edge_percent, 3)}%`
                    : "—"}
                </td>
                <td>
                  <Badge source={p.source} stale={p.stale} />
                </td>
                {mode === "Watchlist" && (
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Move ${p.symbol} up`}
                      onClick={() => onReorder(p.symbol, -1)}
                    >
                      <ArrowUp size={12} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`Move ${p.symbol} down`}
                      onClick={() => onReorder(p.symbol, 1)}
                    >
                      <ArrowDown size={12} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && (
        <Empty
          title={
            tab === "India stocks" || tab === "Indices"
              ? "Market feed not configured"
              : "No matching instruments"
          }
          detail={
            tab === "India stocks" || tab === "Indices"
              ? "Licensed market data is required for this view. No prices or trading-session status are fabricated."
              : "Adjust your filters, or add instruments using the star in Markets."
          }
        />
      )}
    </section>
  );
}
export function ArbitrageTable({
  data,
  connected,
  onSelect,
}: {
  data: Snapshot;
  connected: boolean;
  onSelect: (o: Opportunity) => void;
}) {
  const [type, setType] = useState("all"),
    [edge, setEdge] = useState(0),
    [conf, setConf] = useState(0),
    [liq, setLiq] = useState(0),
    [assetClass, setAssetClass] = useState("All");
  const ops = data.opportunities.filter(
    (o) =>
      (type === "all" || o.type === type) &&
      o.net_edge_percent >= edge &&
      o.confidence_score >= conf &&
      o.liquidity_score >= liq &&
      (assetClass === "All" ||
        (assetClass === "Stocks"
          ? o.type === "cross_venue"
          : o.type !== "cross_venue")),
  );
  return (
    <>
      <LiveArbitrage data={data} connected={connected} onSelect={onSelect} />
      <div className="kpi-grid">
        <div>
          <span>QUALIFIED OPPORTUNITIES</span>
          <strong>{ops.length.toString().padStart(2, "0")}</strong>
          <small>After all risk checks</small>
        </div>
        <div>
          <span>BEST NET EDGE</span>
          <strong className="gold">
            {fmt(Math.max(0, ...ops.map((o) => o.net_edge_percent)), 3)}
            <em>%</em>
          </strong>
          <small>Net of costs · includes capital reserve</small>
        </div>
        <div>
          <span>DETECTION LATENCY</span>
          <strong>
            {fmt(data.detection_ms, 1)}
            <em>ms</em>
          </strong>
          <small>Measured calculation time</small>
        </div>
        <div>
          <span>EXCLUDED CANDIDATES</span>
          <strong>{data.rejected}</strong>
          <small>Risk filters / insufficient depth</small>
        </div>
      </div>
      <section className="panel">
        <PanelHead
          title="Opportunity intelligence"
          sub="Quotes → VWAP → costs → risk → ranked net edge"
          action={<span className="badge gold">PAPER ONLY</span>}
        />
        <div className="filter-bar">
          <div className="tabs">
            {["all", "cross_exchange", "triangular", "cross_venue"].map((t) => (
              <button
                key={t}
                className={type === t ? "active" : ""}
                onClick={() => setType(t)}
              >
                {label(t)}
              </button>
            ))}
          </div>
          <select
            aria-label="Asset class"
            value={assetClass}
            onChange={(e) => setAssetClass(e.target.value)}
          >
            {["All", "Crypto", "Stocks"].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <label>
            Min edge %{" "}
            <input
              aria-label="Minimum net edge"
              type="number"
              min="0"
              step=".01"
              value={edge}
              onChange={(e) => setEdge(+e.target.value)}
            />
          </label>
          <label>
            Confidence{" "}
            <input
              type="number"
              min="0"
              max="100"
              value={conf}
              onChange={(e) => setConf(+e.target.value)}
            />
          </label>
          <label>
            Liquidity{" "}
            <input
              type="number"
              min="0"
              max="100"
              value={liq}
              onChange={(e) => setLiq(+e.target.value)}
            />
          </label>
        </div>
        <div className="table-scroll">
          <table className="op-table">
            <thead>
              <tr>
                {[
                  "ASSET / STRATEGY",
                  "BUY → SELL",
                  "BUY PRICE",
                  "SELL PRICE",
                  "RAW SPREAD",
                  "FEES",
                  "SLIPPAGE",
                  "NET EDGE",
                  "LIQUIDITY",
                  "CONFIDENCE",
                  "AGE",
                  "",
                ].map((h, i) => (
                  <th key={i}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ops.slice(0, 100).map((o) => (
                <tr key={o.id}>
                  <td>
                    <b>{o.symbol}</b>
                    <small>
                      {label(o.type)} · {(o.source === "demo" ? "SIMULATED" : o.source.toUpperCase())}
                    </small>
                  </td>
                  <td>
                    <span>{o.buy_venue}</span>
                    <small>→ {o.sell_venue}</small>
                  </td>
                  <td className="mono">{fmt(o.buy_price, 4)}</td>
                  <td className="mono">{fmt(o.sell_price, 4)}</td>
                  <td className="mono">{fmt(o.gross_spread_percent, 3)}%</td>
                  <td className="mono">
                    {fmt(o.buy_fee + o.sell_fee, 3)}
                    <small>{o.quote}</small>
                  </td>
                  <td className="mono">
                    {fmt(o.estimated_slippage, 3)}
                    <small>{o.quote}</small>
                  </td>
                  <td className="positive mono emphasis">
                    +{fmt(o.net_edge_percent, 3)}%
                  </td>
                  <td>
                    {compact(o.available_liquidity)}
                    <small>{o.quote}</small>
                  </td>
                  <td>
                    <Score value={o.confidence_score} />
                  </td>
                  <td className="mono">
                    {fmt((o.timestamp - o.first_seen) / 1000, 1)}s
                  </td>
                  <td>
                    <button className="view-button" onClick={() => onSelect(o)}>
                      Trade <ArrowUpRight size={12} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!ops.length && (
          <Empty
            title="No routes pass your filters"
            detail="Try a lower display threshold. Server-side risk limits always apply."
          />
        )}
      </section>
      <div className="two-grid">
        <section className="panel">
          <PanelHead title="Best net edge" sub="Rolling session · percent" />
          <StreamChart data={data.history} />
        </section>
        <section className="panel">
          <PanelHead
            title="Opportunity frequency"
            sub="Qualified routes per scan"
          />
          <StreamChart data={data.history} field="count" color="#78bac7" />
        </section>
      </div>
    </>
  );
}
export function PaperPortfolio({ data }: { data: Snapshot }) {
  const p = data.portfolio;
  return (
    <>
      <div className="notice">
        <span className="gold">PAPER TRADING / SIMULATION</span>
        <span>
          USDT ledger · prefunded inventory assumption · simulated fills only
        </span>
      </div>
      <div className="kpi-grid">
        <div>
          <span>PORTFOLIO VALUE</span>
          <strong>{fmt(p.available_capital)}</strong>
          <small>USDT · available simulated capital</small>
        </div>
        <div>
          <span>REALIZED P&L</span>
          <strong className="positive">+{fmt(p.realized_pnl)}</strong>
          <small>Unrealized {fmt(p.unrealized_pnl)} USDT</small>
        </div>
        <div>
          <span>WIN RATE</span>
          <strong>
            {fmt(p.win_rate, 1)}
            <em>%</em>
          </strong>
          <small>{p.number_of_trades} closed simulations</small>
        </div>
        <div>
          <span>MAXIMUM DRAWDOWN</span>
          <strong>
            {fmt(p.maximum_drawdown, 2)}
            <em>%</em>
          </strong>
          <small>Average return {fmt(p.average_return, 3)}%</small>
        </div>
      </div>
      <section className="panel">
        <PanelHead
          title="Simulated P&L"
          sub="USDT · cumulative realized returns this session"
        />
        <StreamChart
          data={data.history}
          field="pnl"
          color="#71bda9"
          height={230}
        />
      </section>
      <section className="panel">
        <PanelHead
          title="Execution ledger"
          sub="Atomic paper fills · no open positions · other quote currencies have separate ledgers"
          action={<span className="count">{data.trades.length}</span>}
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {[
                  "TIME",
                  "ASSET",
                  "STRATEGY",
                  "ROUTE",
                  "CAPITAL",
                  "FEES",
                  "NET P&L",
                  "ROI",
                  "STATUS",
                ].map((t) => (
                  <th key={t}>{t}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.trades.map((t) => (
                <tr key={t.id}>
                  <td>{time(t.timestamp)}</td>
                  <td>
                    <b>{t.symbol}</b>
                  </td>
                  <td className="capitalize">{label(t.type)}</td>
                  <td>
                    {t.buy_venue} → {t.sell_venue}
                  </td>
                  <td>
                    {fmt(t.capital_required)} {t.quote}
                  </td>
                  <td>{fmt(t.fees, 4)}</td>
                  <td className="positive">
                    +{fmt(t.net_profit, 4)} {t.quote}
                  </td>
                  <td>{fmt(t.roi, 3)}%</td>
                  <td>
                    <span className="badge gold">SIMULATED</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!data.trades.length && (
          <Empty
            title="Your first paper trade starts with an edge"
            detail="Open an opportunity in Arbitrage, inspect the cost breakdown, and select Paper execute."
          />
        )}
      </section>
    </>
  );
}
export function Analytics({ data }: { data: Snapshot }) {
  const [result, setResult] = useState<unknown>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function replay(file: File) {
    setBusy(true);
    setError("");
    try {
      const frames = JSON.parse(await file.text());
      const r = await request("/backtest", {
        method: "POST",
        body: JSON.stringify({
          frames: Array.isArray(frames) ? frames : frames.frames,
        }),
      });
      setResult(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="two-grid">
        <section className="panel">
          <PanelHead
            title="Net edge history"
            sub="Qualified opportunities · session"
          />
          <StreamChart data={data.history} />
        </section>
        <section className="panel">
          <PanelHead
            title="Opportunity frequency"
            sub="Routes passing risk filters"
          />
          <StreamChart data={data.history} field="count" color="#78bac7" />
        </section>
        <section className="panel">
          <PanelHead
            title="Asset distribution"
            sub="Active routes by instrument"
          />
          <Bars
            data={Object.entries(
              data.opportunities.reduce<Record<string, number>>((a, o) => {
                a[o.symbol] = (a[o.symbol] || 0) + 1;
                return a;
              }, {}),
            )
              .slice(0, 8)
              .map(([name, value]) => ({ name: name.split("/")[0], value }))}
          />
        </section>
        <section className="panel">
          <PanelHead
            title="Opportunity lifetime"
            sub="Current qualified routes · seconds"
          />
          <Bars
            color="#d4b36b"
            data={data.opportunities
              .slice(0, 8)
              .map((o) => ({
                name: o.symbol.split("/")[0],
                value: (o.timestamp - o.first_seen) / 1000,
              }))}
          />
        </section>
      </div>
      <section className="panel">
        <PanelHead
          title="Liquidity heatmap"
          sub="Displayed depth by venue · quote USDT"
        />
        <div className="heatmap">
          {data.prices
            .filter((p) => p.quote === "USDT")
            .slice(0, 30)
            .map((p) => (
              <div
                key={`${p.exchange}:${p.symbol}`}
                style={{
                  background: `rgba(113,189,169,${Math.min(0.3, p.depth_notional / 4000000)})`,
                }}
              >
                <small>
                  {p.symbol} · {p.exchange}
                </small>
                <b>{compact(p.depth_notional)}</b>
              </div>
            ))}
        </div>
      </section>
      <section className="panel">
        <PanelHead
          title="Historical replay"
          sub="Upload chronological JSON arrays of full order-book snapshots"
        />
        <div className="backtest">
          <p>
            Reuses the production detector and cost model. One ranked simulation
            per frame. Currencies remain separate; the Sharpe-like metric is not
            annualized.
          </p>
          <label className="secondary-button">
            {busy ? "Processing…" : "Import historical JSON"}
            <input
              disabled={busy}
              type="file"
              accept=".json"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) replay(f);
              }}
            />
          </label>
          {error && <p className="error">{error}</p>}
          {result != null && <pre>{JSON.stringify(result, null, 2)}</pre>}
        </div>
      </section>
    </>
  );
}
