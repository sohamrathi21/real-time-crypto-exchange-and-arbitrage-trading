import { ArbitrageDemo } from "./arbitrage-demo";
import { IndianStocks } from "./india";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bell,
  Bitcoin,
  Building2,
  ChevronLeft,
  ChevronRight,
  Command,
  ExternalLink,
  Globe2,
  Layers3,
  LayoutDashboard,
  ListFilter,
  PanelLeftClose,
  Search,
  Settings2,
  CreditCard,
  Newspaper,
  Earth,
  Sun,
  Moon,
  ShieldCheck,
  Star,
  Wallet,
  X,
  Zap,
} from "lucide-react";
import { useMarket, fmt, compact, time } from "./api";
import {
  Badge,
  BookPanel,
  Empty,
  InstrumentChart,
  names,
  OpportunityDetail,
  PanelHead,
  Radar,
} from "./panels";
import {
  Analytics,
  ArbitrageTable,
  MarketTable,
  PaperPortfolio,
} from "./tables";
import {
  AutomationCenter,
  TradingTerminal,
  SystemMonitor,
  ReplayControls,
  type ExtendedSnapshot,
} from "./execution";
import { Landing, NewsHub } from "./discover";
import { Subscription } from "./subscription";
import { NewsCenter, RegionsView, KiteTrading } from "./world";
import type { Opportunity, Price } from "./types";
const modules = [
  ["Home", Globe2],
  ["Terminal", LayoutDashboard],
  ["Markets", Globe2],
  ["Market News", Newspaper],
  ["Continents", Earth],
  ["Live Trading", BarChart3],
  ["Subscription", CreditCard],
  ["Arbitrage", Zap],
  ["Crypto", Bitcoin],
  ["Stocks", Building2],
  ["Indian Stocks", Building2],
  ["Watchlist", Star],
  ["Order Book", Layers3],
  ["Market Scanner", ListFilter],
  ["Paper Trading", Wallet],
  ["Portfolio", ShieldCheck],
  ["Analytics", BarChart3],
  ["Alerts", Bell],
  ["Workspace", PanelLeftClose],
  ["Automation", Settings2],
  ["System", Activity],
] as const;
function readStored<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}
function store(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* Storage-restricted browsers can still use the current session. */
  }
}
export default function App() {
  const { data, connected, error } = useMarket();
  const [page, setPage] = useState(
      () => decodeURIComponent(location.hash.slice(1)) || "Home",
    ),
    [collapsed, setCollapsed] = useState(false),
    [selected, setSelected] = useState({
      symbol: "BTC/USDT",
      exchange: "Binance",
    }),
    [detail, setDetail] = useState<Opportunity | null>(null),
    [search, setSearch] = useState(false),
    [query, setQuery] = useState(""),
    [cursor, setCursor] = useState(0),
    [settings, setSettings] = useState(false),
    [now, setNow] = useState(Date.now()),
    [layout, setLayout] = useState("Focus"),
    [movers, setMovers] = useState("Widest spread"),
    [ticker, setTicker] = useState(() => readStored("ax-ticker", true));
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    readStored("ax-theme", "light"),
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    store("ax-theme", theme);
  }, [theme]);
  const [watch, setWatch] = useState<string[]>(() =>
    readStored("ax-watchlist", [
      "BTC/USDT",
      "ETH/USDT",
      "SOL/USDT",
      "AAPL/USD",
      "NVDA/USD",
    ]),
  );
  const [alertEdge, setAlertEdge] = useState(() =>
      readStored("ax-alert-edge", 0.1),
    ),
    [alertConf, setAlertConf] = useState(() => readStored("ax-alert-conf", 85)),
    [alertAsset, setAlertAsset] = useState(""),
    [alertVenue, setAlertVenue] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const navigate = useCallback((name: string) => {
    setPage(name);
    location.hash = encodeURIComponent(name);
    setSearch(false);
    setQuery("");
    setCursor(0);
  }, []);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    const hash = () =>
      setPage(decodeURIComponent(location.hash.slice(1)) || "Home");
    window.addEventListener("hashchange", hash);
    return () => {
      clearInterval(timer);
      window.removeEventListener("hashchange", hash);
    };
  }, []);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearch((s) => !s);
        setCursor(0);
      }
      if (e.key === "Escape") {
        setSearch(false);
        setDetail(null);
        setSettings(false);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    if (search) input.current?.focus();
  }, [search]);
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [page]);
  useEffect(() => store("ax-watchlist", watch), [watch]);
  useEffect(() => {
    store("ax-alert-edge", alertEdge);
    store("ax-alert-conf", alertConf);
    store("ax-ticker", ticker);
  }, [alertEdge, alertConf, ticker]);
  const unique = useMemo(
    () =>
      data?.prices.filter(
        (p, i, all) =>
          p.quote !== "BTC" &&
          all.findIndex((x) => x.symbol === p.symbol) === i,
      ) || [],
    [data?.prices],
  );
  const price =
    data?.prices.find(
      (p) => p.symbol === selected.symbol && p.exchange === selected.exchange,
    ) || unique.find((p) => p.symbol === selected.symbol);
  const openInstrument = (p: Price) => {
    setSelected({ symbol: p.symbol, exchange: p.exchange });
    navigate("Instrument");
  };
  const toggleWatch = (s: string) =>
    setWatch((w) => (w.includes(s) ? w.filter((x) => x !== s) : [...w, s]));
  const reorder = (s: string, d: number) =>
    setWatch((w) => {
      const next = [...w],
        i = next.indexOf(s),
        j = i + d;
      if (j < 0 || j >= w.length) return w;
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  const results = [
    ...modules
      .filter(([name]) =>
        `go to ${name}`.toLowerCase().includes(query.toLowerCase()),
      )
      .map(([name, Icon]) => ({
        label: name,
        sub: "Open workspace",
        Icon,
        run: () => navigate(name),
      })),
    ...unique
      .filter((p) =>
        `open ${p.symbol} ${names[p.base] || ""} ${p.exchange}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      )
      .map((p) => ({
        label: p.symbol,
        sub: `${names[p.base] || p.base} · ${p.exchange} · ${(p.source === "demo" ? "SIMULATED" : p.source.toUpperCase())}`,
        Icon: Search,
        run: () => openInstrument(p),
      })),
    ...(data
      ? Object.keys(data.venues)
          .filter((v) => v.toLowerCase().includes(query.toLowerCase()))
          .map((v) => ({
            label: `Search ${v}`,
            sub: "Open venue order book",
            Icon: Layers3,
            run: () => {
              const p = data.prices.find((p) => p.exchange === v);
              if (p) setSelected({ symbol: p.symbol, exchange: p.exchange });
              navigate("Order Book");
            },
          }))
      : []),
  ].slice(0, 14);
  const stale = !data || now - data.timestamp > 5000;
  const ops = stale ? [] : data.opportunities;
  const activeDetail =
    detail && (ops.find((o) => o.id === detail.id) || detail);
  const shownMovers = [...unique]
    .sort((a, b) =>
      movers === "Highest liquidity"
        ? b.depth_notional - a.depth_notional
        : b.spread_percent - a.spread_percent,
    )
    .slice(0, 5);
  const marketsTable = (mode: string) => (
    <MarketTable
      key={mode}
      data={data!}
      mode={mode}
      onOpen={openInstrument}
      watch={watch}
      onWatch={toggleWatch}
      onReorder={reorder}
    />
  );
  const watchPanel = (
    <section className="panel">
      <PanelHead
        title="Watchlist"
        sub="Your markets, in one place"
        action={
          <button
            className="icon-button"
            aria-label="Add asset"
            onClick={() => {
              setSearch(true);
              setQuery("");
            }}
          >
            <span className="gold">+</span>
          </button>
        }
      />
      <div className="mini-head">
        <span>INSTRUMENT</span>
        <span>PRICE</span>
        <span>SPREAD</span>
      </div>
      {watch.slice(0, 5).map((s) => {
        const p = unique.find((p) => p.symbol === s);
        return (
          p && (
            <button
              className="mini-row"
              key={s}
              onClick={() => openInstrument(p)}
            >
              <span>
                <b>{p.base}</b>
                <small>{names[p.base] || p.symbol}</small>
              </span>
              <b className="mono">{fmt(p.price, p.price < 1 ? 4 : 2)}</b>
              <span className="muted mono">{fmt(p.spread_percent, 3)}%</span>
            </button>
          )
        );
      })}
      {!watch.length && (
        <Empty
          title="Build your watchlist"
          detail="Star any instrument in Markets to follow it here."
        />
      )}
      <button className="panel-link" onClick={() => navigate("Watchlist")}>
        Manage watchlist <ChevronRight size={13} />
      </button>
    </section>
  );
  if (page === "Home") return <Landing navigate={navigate} theme={theme} setTheme={setTheme} data={data} />;
  return (
    <div className={`app-shell ${collapsed ? "collapsed" : ""}`}>
      <header className="topbar">
        <a
          className="brand"
          href="#Terminal"
          onClick={() => navigate("Terminal")}
        >
          <span className="brand-mark">╱╲</span>
          <b>
            ARBITRAGE <em>X</em>
          </b>
        </a>
        <button
          className="global-search"
          onClick={() => {
            setSearch(true);
            setQuery("");
          }}
        >
          <Search size={15} />
          <span>Search stocks, crypto, symbols, exchanges…</span>
          <kbd>⌘ K</kbd>
        </button>
        <div className="top-status">
          <span>
            <i className="dot" />
            CRYPTO 24/7
          </span>
          <span className="muted">
            US <i className="dot off" /> FEED{" "}
            {data?.mode === "demo" ? "SIMULATED" : "N/A"}
          </span>
          <span className="muted india-status">
            <button className="landing-text-button" onClick={() => navigate("Indian Stocks")}>INDIA · NSE</button>
          </span>
        </div>
        <span className={`mode-tag ${data?.mode === "demo" ? "gold" : ""}`}>
          {page === "Live Trading"
            ? "ZERODHA · REAL ORDERS"
            : ["Market News", "Continents"].includes(page)
              ? "PUBLISHER NEWS"
              : data?.mode === "demo"
                ? "SIMULATED MARKET"
                : data?.mode === "replay"
                  ? "REPLAY"
                  : "MARKET FEEDS"}
        </span>
        <button
          className="icon-button theme-toggle"
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <button
          className="icon-button"
          aria-label="Settings"
          onClick={() => setSettings(true)}
        >
          <Settings2 size={17} />
        </button>
      </header>
      <aside className="sidebar">
        <div className="sidebar-label">WORKSPACE</div>
        <nav>
          {modules.map(([name, Icon], index) => (
            <div key={name}>
              {index === 6 && (
                <div className="sidebar-divider">
                  <span>INTELLIGENCE & EXECUTION</span>
                </div>
              )}
              <button
                title={name}
                className={page === name ? "active" : ""}
                onClick={() => navigate(name)}
              >
                <Icon size={16} />
                <span>{name}</span>
                {name === "Arbitrage" && <em>{ops.length}</em>}
                {name === "Alerts" && data?.alerts.length ? (
                  <i className="tiny-dot" />
                ) : null}
              </button>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="simulation-card">
            <ShieldCheck size={17} />
            <strong>Paper trading</strong>
            <small>
              Explore the edge.
              <br />
              Keep your capital safe.
            </small>
          </div>
          <button
            className="collapse-button"
            onClick={() => setCollapsed((c) => !c)}
            aria-label="Toggle sidebar"
          >
            {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
            <span>Collapse sidebar</span>
          </button>
          <div className="user">
            <span>S</span>
            <div>Research workspace</div>
          </div>
        </div>
      </aside>
      <div className="workspace">
        {ticker && (
          <div className="market-ticker">
            {["BTC/USDT", "ETH/USDT", "SOL/USDT", "AAPL/USD", "NVDA/USD"].map(
              (s) => {
                const p = unique.find((p) => p.symbol === s);
                return (
                  <button key={s} onClick={() => p && openInstrument(p)}>
                    <span>{s}</span>
                    <b>{p ? fmt(p.price, p.price < 1 ? 4 : 2) : "—"}</b>
                    <small className="gold">
                      {p ? (p.source === "demo" ? "SIMULATED" : p.source.toUpperCase()) : "NO FEED"}
                    </small>
                  </button>
                );
              },
            )}
            <div className="ticker-unavailable">
              <span>S&P 500 · NIFTY 50</span>
              <b>—</b>
              <small>FEED NOT CONFIGURED</small>
            </div>
          </div>
        )}
        <main>
          <div className="page-header">
            <div>
              <div className="eyebrow">
                MARKET INTELLIGENCE /{" "}
                {page === "Instrument" ? selected.symbol : page.toUpperCase()}
              </div>
              <h1>
                {page === "Terminal"
                  ? "The market, in perspective."
                  : page === "Instrument"
                    ? `${price?.base || selected.symbol} terminal`
                    : page === "Arbitrage"
                      ? "Arbitrage intelligence"
                      : page}
              </h1>
              <p>
                {page === "Terminal"
                  ? "A clearer view of the market. A sharper view of the edge."
                  : page === "Arbitrage"
                    ? "Executable depth. Transparent costs. Measurable confidence."
                    : "A real-time market terminal built around arbitrage intelligence."}
              </p>
            </div>
            <div className="header-meta">
              <span>
                <i className={`dot ${!connected ? "off" : ""}`} />
                {connected ? "STREAM CONNECTED" : "CONNECTING"}
              </span>
              <b>
                {time(now)}{" "}
                <small title="Indian Standard Time · UTC+05:30">IST</small>
              </b>
              <small>
                {new Date(now)
                  .toLocaleDateString("en-GB", {
                    timeZone: "Asia/Kolkata",
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                  })
                  .toUpperCase()}
              </small>
            </div>
          </div>
          {data?.mode === "replay" &&
            ![
              "Market News",
              "Continents",
              "Live Trading",
              "Subscription",
            ].includes(page) && (
              <div className="demo-ribbon">
                <span>REPLAY · RECORDED MARKET DATA</span>
                <span>
                  Historical events replayed through the same quant engine.
                </span>
                <b>PAPER EXECUTION ONLY</b>
              </div>
            )}
          {data?.mode === "demo" &&
            ![
              "Market News",
              "Continents",
              "Live Trading",
              "Subscription",
            ].includes(page) && (
              <div className="demo-ribbon">
                <span>
                  <i className="dot amber" /> SIMULATED MARKET DATA
                </span>
                <span>Practice mode uses simulated prices and funds.</span>
                <b>PAPER TRADING / SIMULATION</b>
              </div>
            )}
          {(error || (stale && data)) && (
            <div className="error banner">
              {error ||
                "Market data is stale. Opportunity execution is disabled until the feed recovers."}
            </div>
          )}
          {page === "Arbitrage" && <ArbitrageDemo />}
          {!data ? (
            <section className="panel">
              <Empty
                title="Connecting to the market engine"
                detail="Start the FastAPI backend on port 8000. Quotes appear only after the data provider connects."
              />
            </section>
          ) : (
            <>
              {page === "Terminal" && (
                <>
                  <div className="home-grid">
                    <InstrumentChart price={price} />
                    <Radar
                      ops={ops}
                      onSelect={setDetail}
                      onAll={() => navigate("Arbitrage")}
                    />
                  </div>
                  <div className="three-grid">
                    <section className="panel">
                      <PanelHead
                        title="Market movers"
                        sub="Ranked from current order books"
                      />
                      <div className="tabs mini-tabs">
                        {["Widest spread", "Highest liquidity"].map((t) => (
                          <button
                            key={t}
                            className={movers === t ? "active" : ""}
                            onClick={() => setMovers(t)}
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                      {shownMovers.map((p, i) => (
                        <button
                          key={p.symbol}
                          className="mover-row"
                          onClick={() => openInstrument(p)}
                        >
                          <small>0{i + 1}</small>
                          <div className={`coin coin-${i}`}>
                            {p.base.slice(0, 1)}
                          </div>
                          <span>
                            <b>{p.base}</b>
                            <small>{names[p.base] || p.base}</small>
                          </span>
                          <b className="mono">
                            {movers === "Highest liquidity"
                              ? compact(p.depth_notional)
                              : fmt(p.spread_percent, 3) + "%"}
                            <small>
                              {movers === "Highest liquidity"
                                ? p.quote
                                : "bid / ask spread"}
                            </small>
                          </b>
                        </button>
                      ))}
                    </section>
                    {watchPanel}
                    <section className="panel">
                      <PanelHead
                        title="Market activity"
                        sub="Feed health & engine events"
                        action={<Activity size={15} className="muted" />}
                      />
                      <div className="feed-list">
                        {Object.entries(data.venues)
                          .filter(([name]) => !name.endsWith("-SIM"))
                          .slice(0, 5)
                          .map(([name, s]) => (
                            <div key={name}>
                              <span>
                                <i
                                  className={`dot ${s.state === "disconnected" ? "off" : ""}`}
                                />
                                {name}
                              </span>
                              <span className="mono muted">
                                {s.latency_ms
                                  ? fmt(s.latency_ms, 0) + " ms"
                                  : "—"}{" "}
                                <Badge source={s.source} />
                              </span>
                            </div>
                          ))}
                      </div>
                      <div className="activity-note">
                        <span className="gold">ENGINE STATUS</span>
                        <p>
                          {ops.length} qualified routes across{" "}
                          {data.prices.length} order books.
                        </p>
                        <small>
                          Detection {fmt(data.detection_ms, 1)} ms · Redis{" "}
                          {data.redis}
                        </small>
                      </div>
                      <button
                        className="panel-link"
                        onClick={() => navigate("Alerts")}
                      >
                        View system events <ChevronRight size={13} />
                      </button>
                    </section>
                  </div>
                </>
              )}
              {page === "Indian Stocks" && <IndianStocks />}
              {page === "Market News" && <NewsHub />}
              {page === "Continents" && <RegionsView />}
              {page === "Live Trading" && <KiteTrading />}
              {page === "Subscription" && <Subscription />}
              {[
                "Markets",
                "Crypto",
                "Stocks",
                "Watchlist",
                "Market Scanner",
              ].includes(page) && marketsTable(page)}
              {page === "Arbitrage" && (
                <ArbitrageTable
                  connected={connected}
                  data={{ ...data, opportunities: ops }}
                  onSelect={setDetail}
                />
              )}
              {page === "Instrument" && (
                <>
                  <div className="instrument-controls">
                    <select
                      aria-label="Select instrument"
                      value={selected.symbol}
                      onChange={(e) =>
                        setSelected((s) => ({ ...s, symbol: e.target.value }))
                      }
                    >
                      {unique.map((p) => (
                        <option key={p.symbol}>{p.symbol}</option>
                      ))}
                    </select>
                    <select
                      aria-label="Select venue"
                      value={price?.exchange}
                      onChange={(e) =>
                        setSelected((s) => ({ ...s, exchange: e.target.value }))
                      }
                    >
                      {data.prices
                        .filter((p) => p.symbol === selected.symbol)
                        .map((p) => (
                          <option key={p.exchange}>{p.exchange}</option>
                        ))}
                    </select>
                    <button
                      className="secondary-button"
                      onClick={() => toggleWatch(selected.symbol)}
                    >
                      <Star size={13} />{" "}
                      {watch.includes(selected.symbol)
                        ? "Remove from watchlist"
                        : "Add to watchlist"}
                    </button>
                    <button
                      className="secondary-button"
                      onClick={() => navigate("Paper Trading")}
                    >
                      Paper order ticket
                    </button>
                    <button
                      className="secondary-button"
                      onClick={() => navigate("Order Book")}
                    >
                      Open order book <ArrowRight size={13} />
                    </button>
                  </div>
                  <div className="home-grid">
                    <InstrumentChart price={price} />
                    <Radar
                      ops={ops.filter(
                        (o) =>
                          o.symbol === selected.symbol ||
                          o.path.includes(price?.base || ""),
                      )}
                      onSelect={setDetail}
                      onAll={() => navigate("Arbitrage")}
                    />
                  </div>
                  <section className="panel">
                    <PanelHead
                      title="Venue comparison"
                      sub="Same instrument and quote currency · displayed order-book prices"
                    />
                    <div className="venue-comparison">
                      {data.prices
                        .filter((p) => p.symbol === selected.symbol)
                        .map((p) => {
                          const same = data.prices.filter(
                            (x) =>
                              x.symbol === selected.symbol &&
                              x.source === p.source,
                          );
                          return (
                            <button
                              key={p.exchange}
                              onClick={() =>
                                setSelected((s) => ({
                                  ...s,
                                  exchange: p.exchange,
                                }))
                              }
                            >
                              <span>
                                {p.exchange}
                                <Badge source={p.source} stale={p.stale} />
                              </span>
                              <strong>{fmt(p.price, 4)}</strong>
                              <small>
                                BID {fmt(p.bid, 4)} · ASK {fmt(p.ask, 4)}
                              </small>
                              <em className="positive">
                                {p.ask === Math.min(...same.map((x) => x.ask))
                                  ? "LOWEST ASK"
                                  : p.bid ===
                                      Math.max(...same.map((x) => x.bid))
                                    ? "HIGHEST BID"
                                    : " "}
                              </em>
                            </button>
                          );
                        })}
                    </div>
                  </section>
                </>
              )}
              {page === "Order Book" && (
                <>
                  <div className="instrument-controls">
                    <select
                      aria-label="Order book instrument"
                      value={selected.symbol}
                      onChange={(e) =>
                        setSelected((s) => ({ ...s, symbol: e.target.value }))
                      }
                    >
                      {unique.map((p) => (
                        <option key={p.symbol}>{p.symbol}</option>
                      ))}
                    </select>
                    <select
                      aria-label="Order book venue"
                      value={price?.exchange}
                      onChange={(e) =>
                        setSelected((s) => ({ ...s, exchange: e.target.value }))
                      }
                    >
                      {data.prices
                        .filter((p) => p.symbol === selected.symbol)
                        .map((p) => (
                          <option key={p.exchange}>{p.exchange}</option>
                        ))}
                    </select>
                  </div>
                  <BookPanel price={price} />
                </>
              )}
              {page === "Portfolio" && <PaperPortfolio data={data} />}
              {page === "Paper Trading" && (
                <TradingTerminal
                  data={data as ExtendedSnapshot}
                  price={price}
                  onPrice={(p) =>
                    setSelected({ symbol: p.symbol, exchange: p.exchange })
                  }
                  onOpportunity={setDetail}
                />
              )}
              {page === "Analytics" && (
                <>
                  <ReplayControls data={data as ExtendedSnapshot} />
                  <Analytics data={data} />
                  <SystemMonitor
                    data={data as ExtendedSnapshot}
                    connected={connected}
                  />
                </>
              )}
              {page === "Automation" && (
                <AutomationCenter data={data as ExtendedSnapshot} />
              )}
              {page === "System" && (
                <SystemMonitor
                  data={data as ExtendedSnapshot}
                  connected={connected}
                />
              )}
              {page === "Trading" && (
                <TradingTerminal
                  data={data as ExtendedSnapshot}
                  price={price}
                  onPrice={(p) =>
                    setSelected({ symbol: p.symbol, exchange: p.exchange })
                  }
                  onOpportunity={setDetail}
                />
              )}
              {page === "Alerts" && (
                <>
                  <section className="panel">
                    <PanelHead
                      title="Alert preferences"
                      sub="Opportunity radar alerts are filtered below; feed and risk events always remain visible"
                    />
                    <div className="filter-bar">
                      <label>
                        Min edge %
                        <input
                          type="number"
                          min="0"
                          step=".01"
                          value={alertEdge}
                          onChange={(e) => setAlertEdge(+e.target.value)}
                        />
                      </label>
                      <label>
                        Min confidence
                        <input
                          type="number"
                          min="0"
                          max="100"
                          value={alertConf}
                          onChange={(e) => setAlertConf(+e.target.value)}
                        />
                      </label>
                      <input
                        aria-label="Alert asset"
                        placeholder="Asset, e.g. BTC"
                        value={alertAsset}
                        onChange={(e) => setAlertAsset(e.target.value)}
                      />
                      <select
                        aria-label="Alert venue"
                        value={alertVenue}
                        onChange={(e) => setAlertVenue(e.target.value)}
                      >
                        <option value="">All exchanges</option>
                        {Object.keys(data.venues).map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </div>
                    {ops
                      .filter(
                        (o) =>
                          o.net_edge_percent >= alertEdge &&
                          o.confidence_score >= alertConf &&
                          o.symbol.includes(alertAsset.toUpperCase()) &&
                          (!alertVenue ||
                            o.buy_venue === alertVenue ||
                            o.sell_venue === alertVenue),
                      )
                      .slice(0, 8)
                      .map((o) => (
                        <button
                          className="alert-row"
                          key={o.id}
                          onClick={() => setDetail(o)}
                        >
                          <Zap size={16} className="gold" />
                          <span>
                            <b>
                              {o.symbol} · +{fmt(o.net_edge_percent, 3)}% net
                            </b>
                            <small>
                              {o.buy_venue} → {o.sell_venue} · confidence{" "}
                              {o.confidence_score}
                            </small>
                          </span>
                          <Badge source={o.source} />
                        </button>
                      ))}
                  </section>
                  <section className="panel">
                    <PanelHead
                      title="System event log"
                      sub="Opportunity expiration, feed changes, risk checks, and errors"
                    />
                    {data.alerts
                      .filter((a) => a.kind !== "opportunity")
                      .slice(0, 40)
                      .map((a) => (
                        <div className="alert-row" key={a.id}>
                          <Activity
                            size={14}
                            className={
                              a.kind === "error" ? "negative" : "muted"
                            }
                          />
                          <span>
                            <b className="capitalize">{a.kind}</b>
                            <small>{a.message}</small>
                          </span>
                          <time>{time(a.timestamp)}</time>
                        </div>
                      ))}
                  </section>
                </>
              )}
              {page === "Workspace" && (
                <>
                  <div className="tabs workspace-presets">
                    {["Focus", "Research", "Execution"].map((l) => (
                      <button
                        key={l}
                        onClick={() => setLayout(l)}
                        className={layout === l ? "active" : ""}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                  <div className="two-grid">
                    <InstrumentChart price={price} small />
                    {layout === "Research" ? (
                      <BookPanel price={price} />
                    ) : (
                      <Radar
                        ops={ops}
                        onSelect={setDetail}
                        onAll={() => navigate("Arbitrage")}
                      />
                    )}
                    {layout !== "Focus" && watchPanel}
                    {layout === "Execution" && (
                      <section className="panel">
                        <PanelHead title="Paper portfolio" />
                        <div className="workspace-equity">
                          <span>AVAILABLE CAPITAL · USDT</span>
                          <strong>
                            {fmt(data.portfolio.available_capital)}
                          </strong>
                          <p className="positive">
                            +{fmt(data.portfolio.realized_pnl)} realized P&L
                          </p>
                          <button
                            className="secondary-button"
                            onClick={() => navigate("Paper Trading")}
                          >
                            Open execution ledger
                          </button>
                        </div>
                      </section>
                    )}
                  </div>
                </>
              )}
            </>
          )}
          <footer className="disclaimer">
            This application is an market research and paper-trading system.
            The built-in engine simulates trades; the separate Zerodha flow lets
            you place real orders in Kite. This application does not constitute
            financial advice. Market data may be delayed, simulated, incomplete,
            or subject to provider limitations.
          </footer>
        </main>
      </div>
      <div className="statusbar">
        <span>
          <i className={`dot ${connected && !stale ? "" : "off"}`} /> DATA FEED{" "}
          {connected && !stale ? "CONNECTED" : "OFFLINE / STALE"}
        </span>
        <span>
          DETECTION <b>{data ? fmt(data.detection_ms, 1) : "—"} ms</b>
        </span>
        <span>
          BOOKS <b>{data?.prices.length || 0}</b>
        </span>
        <span>
          OPPORTUNITIES{" "}
          <b className="gold">{ops.length.toString().padStart(2, "0")}</b>
        </span>
        <div />
        <span>
          WEBSOCKET <b>{connected ? "CONNECTED" : "RETRYING"}</b>
        </span>
        <span>
          LAST UPDATE{" "}
          <b>{data ? Math.max(0, now - data.timestamp) + " ms" : "—"}</b>
        </span>
        <span className="gold">
          {page === "Live Trading" ? "REAL ORDERS IN KITE" : "PAPER ENGINE"}
        </span>
      </div>
      {activeDetail && (
        <OpportunityDetail
          key={activeDetail.id}
          op={activeDetail}
          current={ops.some((o) => o.id === activeDetail.id)}
          onClose={() => setDetail(null)}
          connected={connected && !stale}
        />
      )}
      {search && (
        <div
          className="overlay search-overlay"
          onClick={() => setSearch(false)}
        >
          <section
            className="command-center"
            role="dialog"
            aria-modal="true"
            aria-label="Command center"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="command-input">
              <Search size={19} />
              <input
                ref={input}
                placeholder="Search an asset, exchange, or command…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setCursor(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setCursor((c) => Math.min(c + 1, results.length - 1));
                  }
                  if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setCursor((c) => Math.max(0, c - 1));
                  }
                  if (e.key === "Enter") results[cursor]?.run();
                }}
              />
              <kbd>ESC</kbd>
            </div>
            <div className="eyebrow command-title">COMMAND CENTER</div>
            <div className="command-results">
              {results.map((r, i) => (
                <button
                  key={r.label}
                  onMouseEnter={() => setCursor(i)}
                  className={i === cursor ? "active" : ""}
                  onClick={r.run}
                >
                  <r.Icon size={17} />
                  <span>
                    <b>{r.label}</b>
                    <small>{r.sub}</small>
                  </span>
                  <ChevronRight size={14} />
                </button>
              ))}
              {!results.length && (
                <Empty
                  title="No matching markets"
                  detail="Only instruments supplied by connected providers appear here."
                />
              )}
            </div>
            <div className="command-footer">
              <span>↑ ↓ to navigate</span>
              <span>↵ to open</span>
              <span>esc to close</span>
            </div>
          </section>
        </div>
      )}
      {settings && (
        <div className="overlay" onClick={() => setSettings(false)}>
          <section
            className="settings-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Settings"
            onClick={(e) => e.stopPropagation()}
          >
            <PanelHead
              title="Terminal settings"
              sub="Risk settings are server-enforced"
              action={
                <button
                  aria-label="Close settings"
                  onClick={() => setSettings(false)}
                >
                  <X size={17} />
                </button>
              }
            />
            <div className="settings-body">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={ticker}
                  onChange={(e) => setTicker(e.target.checked)}
                />{" "}
                Show market ticker
              </label>
              <p className="muted">
                Edit backend environment variables and restart to change risk
                limits. Display filters cannot override these limits.
              </p>
              {data &&
                Object.entries(data.settings)
                  .filter(
                    ([k, v]) =>
                      typeof v === "number" && k !== "starting_capital",
                  )
                  .map(([k, v]) => (
                    <div className="setting-row" key={k}>
                      <span>{k.replaceAll("_", " ")}</span>
                      <b>{String(v)}</b>
                    </div>
                  ))}
              <div className="notice">
                Database: {data?.database || "connecting"}
                <br />
                Redis: {data?.redis || "connecting"}
                <br />
                Market session data: US / India unavailable; simulated US
                equities require a connected data provider.
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
