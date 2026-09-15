import { useEffect, useState } from "react";
import {
  ExternalLink,
  Globe2,
  Newspaper,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { request } from "./api";
import { Empty, PanelHead } from "./panels";

type Story = {
  id: string;
  headline: string;
  url: string;
  source: string;
  region: string;
  published_at: number | null;
};
type Feed = {
  source: string;
  region: string;
  status: string;
  fetched_at?: number;
  items: Story[];
};
type News = { feeds: Feed[]; refresh_seconds: number; timestamp: number };
const regions = [
  "All",
  "Global",
  "Asia",
  "Europe",
  "North America",
  "South America",
  "Africa",
  "Oceania",
  "Middle East",
  "Crypto",
];
const ist = (value: number) =>
  new Date(value).toLocaleString("en-GB", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }) + " IST";

export function NewsCenter({
  initialRegion = "All",
}: {
  initialRegion?: string;
}) {
  const [region, setRegion] = useState(initialRegion),
    [data, setData] = useState<News | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [query, setQuery] = useState("");
  useEffect(() => setRegion(initialRegion), [initialRegion]);
  const refresh = async () => {
    setLoading(true);
    try {
      setData(await request<News>("/news"));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "News unavailable");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), 300000);
    return () => clearInterval(id);
  }, []);
  const feeds = (data?.feeds || []).filter(
    (f) => region === "All" || f.region === region,
  );
  const stories = Array.from(
    new Map(
      feeds
        .flatMap((f) => f.items)
        .filter((s) => s.headline.toLowerCase().includes(query.toLowerCase()))
        .map((s) => [s.id, s]),
    ).values(),
  ).sort((a, b) => (b.published_at || 0) - (a.published_at || 0));
  return (
    <section className="panel news-center">
      <PanelHead
        title="Live news desk"
        sub="Publisher headlines · business, crypto and regional developments"
        action={
          <button
            className="secondary-button"
            onClick={() => void refresh()}
            disabled={loading}
          >
            <RefreshCw size={13} />
            {loading ? "Updating…" : "Refresh"}
          </button>
        }
      />
      <div className="news-toolbar">
        <div className="region-tabs">
          {regions.map((r) => (
            <button
              key={r}
              onClick={() => setRegion(r)}
              className={r === region ? "active" : ""}
            >
              {r}
            </button>
          ))}
        </div>
        <input
          aria-label="Search headlines"
          placeholder="Search headlines…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="news-status">
        <span>
          <i className="dot" />
          Publisher feeds refresh every 5 minutes; publication times below.
        </span>
        <span>
          {data && feeds.some((f) => f.fetched_at)
            ? `Fetched ${ist(Math.max(0, ...feeds.map((f) => f.fetched_at || 0)))}`
            : "Fetching publishers…"}
        </span>
      </div>
      {error && <p className="error banner">{error}</p>}
      {feeds.some((f) => f.status !== "available") && (
        <p className="news-notice">
          {feeds
            .filter((f) => f.status !== "available")
            .map((f) => `${f.source}: ${f.status}`)
            .join(" · ")}
          . Cached headlines retain their original publication times.
        </p>
      )}
      <div className="news-grid">
        {stories.map((s) => (
          <a
            className="news-card"
            key={s.id}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <div className="news-art">
              <Newspaper size={25} />
              <span>{s.region}</span>
              <small>
                READ ARTICLE <ExternalLink size={11} />
              </small>
            </div>
            <div className="news-copy">
              <h3>{s.headline}</h3>
              <div>
                <b>{s.source}</b>
                <time
                  dateTime={
                    s.published_at
                      ? new Date(s.published_at).toISOString()
                      : undefined
                  }
                >
                  {s.published_at
                    ? ist(s.published_at)
                    : "Publication time unavailable"}
                </time>
              </div>
            </div>
          </a>
        ))}
      </div>
      {!stories.length && (
        <Empty
          title={
            loading ? "Fetching publisher headlines" : "No matching headlines"
          }
          detail={
            loading
              ? "Connecting to the source feeds."
              : "Try another region or search. No generated headlines are substituted."
          }
        />
      )}
      <p className="news-notice">
        Regional feeds contain wider news as well as business coverage. South
        America uses BBC Latin America coverage; Oceania uses BBC Australia
        coverage. Articles open on their publisher’s website.
      </p>
    </section>
  );
}

type Session = {
  region: string;
  city: string;
  venue: string;
  zone: string;
  open: number;
  close: number;
  url: string;
};
const sessions: Session[] = [
  {
    region: "Asia",
    city: "Mumbai",
    venue: "NSE · cash equities",
    zone: "Asia/Kolkata",
    open: 555,
    close: 930,
    url: "https://www.nseindia.com/static/market-data/market-timings",
  },
  {
    region: "Europe",
    city: "London",
    venue: "LSE · SETS",
    zone: "Europe/London",
    open: 480,
    close: 990,
    url: "https://www.londonstockexchange.com/trade/trading-access/business-days",
  },
  {
    region: "North America",
    city: "New York",
    venue: "NYSE · core equities",
    zone: "America/New_York",
    open: 570,
    close: 960,
    url: "https://www.nyse.com/markets/hours-calendars",
  },
  {
    region: "South America",
    city: "São Paulo",
    venue: "B3 · cash equities",
    zone: "America/Sao_Paulo",
    open: 600,
    close: 1015,
    url: "https://www.b3.com.br/en_us/solutions/platforms/puma-trading-system/for-members-and-traders/trading-hours/equities/",
  },
  {
    region: "Africa",
    city: "Johannesburg",
    venue: "JSE · continuous equities",
    zone: "Africa/Johannesburg",
    open: 540,
    close: 1010,
    url: "https://www.jse.co.za/trade/equity-market",
  },
  {
    region: "Oceania",
    city: "Sydney",
    venue: "ASX · normal trading",
    zone: "Australia/Sydney",
    open: 600,
    close: 960,
    url: "https://www.asx.com.au/markets/market-resources/trading-hours-calendar",
  },
];
function localParts(now: number, zone: string) {
  return Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
      weekday: "short",
    })
      .formatToParts(now)
      .map((p) => [p.type, p.value]),
  );
}
function scheduleTime(now: number, s: Session, minutes: number) {
  const p = localParts(now, s.zone);
  const local = Date.UTC(
    +p.year,
    +p.month - 1,
    +p.day,
    +p.hour,
    +p.minute,
    +p.second,
  );
  const offset = local - Math.floor(now / 1000) * 1000;
  return ist(
    Date.UTC(
      +p.year,
      +p.month - 1,
      +p.day,
      Math.floor(minutes / 60),
      minutes % 60,
    ) - offset,
  );
}
const hm = (n: number) =>
  `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
export function RegionsView() {
  const [now, setNow] = useState(Date.now()),
    [selected, setSelected] = useState("All");
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="world-view">
      <section className="panel">
        <PanelHead
          title="Across the continents"
          sub="One representative equity session per region · daylight-saving aware clocks"
        />
        <div className="session-grid">
          {sessions.map((s) => {
            const p = localParts(now, s.zone),
              min = +p.hour * 60 + +p.minute,
              weekend = ["Sat", "Sun"].includes(p.weekday),
              within = !weekend && min >= s.open && min < s.close;
            return (
              <article
                className={`session-card ${selected === s.region ? "selected" : ""}`}
                key={s.region}
              >
                <div>
                  <Globe2 size={19} />
                  <b>{s.region}</b>
                  <span className={within ? "positive" : "muted"}>
                    {weekend
                      ? "WEEKEND"
                      : within
                        ? "IN REGULAR WINDOW"
                        : "OUTSIDE WINDOW"}
                  </span>
                </div>
                <h2>
                  {p.hour}:{p.minute}
                  <small>:{p.second}</small>
                </h2>
                <p>
                  {s.city} · {s.venue}
                </p>
                <small>
                  {hm(s.open)}–{hm(s.close)} local · weekdays
                </small>
                <p className="session-ist">
                  Today’s window: {scheduleTime(now, s, s.open)} →{" "}
                  {scheduleTime(now, s, s.close)}
                </p>
                <div className="session-actions">
                  <button
                    className="secondary-button"
                    onClick={() => setSelected(s.region)}
                  >
                    Regional news
                  </button>
                  <a href={s.url} target="_blank" rel="noopener noreferrer">
                    Exchange calendar <ExternalLink size={11} />
                  </a>
                </div>
              </article>
            );
          })}
        </div>
        <p className="news-notice">
          Regular-session windows are indicative, not a live exchange-open
          signal. Holidays, special sessions, auctions, halts and seasonal rule
          changes may override them; check the linked exchange calendar.
          Antarctica has no equity exchange session. Crypto markets operate
          around the clock.
        </p>
      </section>
      <NewsCenter initialRegion={selected} />
    </div>
  );
}

export function KiteTrading() {
  const [apiKey, setApiKey] = useState(import.meta.env.VITE_KITE_API_KEY || ""),
    [symbol, setSymbol] = useState(""),
    [exchange, setExchange] = useState("NSE"),
    [side, setSide] = useState("BUY"),
    [type, setType] = useState("LIMIT"),
    [quantity, setQuantity] = useState("1"),
    [price, setPrice] = useState(""),
    [product, setProduct] = useState("CNC"),
    [review, setReview] = useState(false);
  const valid = Boolean(
    apiKey.trim() &&
    /^[A-Z0-9&._-]{1,30}$/.test(symbol) &&
    Number.isInteger(+quantity) &&
    +quantity > 0 &&
    +quantity <= 100000 &&
    (type === "MARKET" || (Number.isFinite(+price) && +price > 0)),
  );
  const basket = [
    {
      variety: "regular",
      tradingsymbol: symbol,
      exchange,
      transaction_type: side,
      order_type: type,
      quantity: +quantity,
      product,
      validity: "DAY",
      ...(type === "LIMIT" ? { price: +price } : {}),
      readonly: true,
      tag: "ArbitrageX",
    },
  ];
  const changed = () => setReview(false);
  return (
    <section className="panel kite-panel">
      <PanelHead
        title="Zerodha Kite · real orders"
        sub="Prepare an Indian equity order, then review and place it securely in Kite"
      />
      <div className="kite-intro">
        <ShieldCheck size={25} />
        <div>
          <h3>Broker order review</h3>
          <p>
            This ticket uses your real Zerodha account. Login, current prices,
            funds checks and final order placement happen in Kite. Paper
            positions and balances are separate.
          </p>
        </div>
        <a
          href="https://kite.zerodha.com"
          target="_blank"
          rel="noopener noreferrer"
          className="secondary-button"
        >
          Open Kite <ExternalLink size={13} />
        </a>
      </div>
      <div className="kite-fields" onChange={changed}>
        <label>
          Kite app public API key
          <input
            aria-label="Kite public API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            autoComplete="off"
            placeholder="Public API key — not API secret"
          />
        </label>
        <label>
          Trading symbol
          <input
            aria-label="Kite trading symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="Exact NSE/BSE symbol"
            maxLength={30}
          />
        </label>
        <label>
          Exchange
          <select
            value={exchange}
            onChange={(e) => setExchange(e.target.value)}
          >
            <option>NSE</option>
            <option>BSE</option>
          </select>
        </label>
        <label>
          Side
          <select value={side} onChange={(e) => setSide(e.target.value)}>
            <option>BUY</option>
            <option>SELL</option>
          </select>
        </label>
        <label>
          Order type
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option>LIMIT</option>
            <option>MARKET</option>
          </select>
        </label>
        <label>
          Quantity
          <input
            aria-label="Kite quantity"
            type="number"
            min="1"
            step="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </label>
        <label>
          Product
          <select value={product} onChange={(e) => setProduct(e.target.value)}>
            <option value="CNC">Delivery (CNC)</option>
            <option value="MIS">Intraday (MIS)</option>
          </select>
        </label>
        {type === "LIMIT" && (
          <label>
            Limit price · INR
            <input
              aria-label="Kite limit price"
              type="number"
              min="0.01"
              step="any"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
            />
          </label>
        )}
      </div>
      <p className="news-notice">
        Your public API key is kept only in this page’s memory. Configure an
        approved app and redirect URL in the{" "}
        <a
          href="https://developers.kite.trade"
          target="_blank"
          rel="noopener noreferrer"
        >
          Kite developer console
        </a>
        . This screen does not receive quotes, order status, holdings or account
        credentials from Kite.
      </p>
      <button
        className="secondary-button kite-review"
        disabled={!valid}
        onClick={() => setReview(true)}
      >
        Review real order
      </button>
      {review && valid && (
        <div className="kite-summary">
          <h3>
            {side} {quantity} × {symbol} · {exchange}
          </h3>
          <p>
            {product} · {type} ·{" "}
            {type === "LIMIT"
              ? `Limit ₹${price}; order value ₹${(+quantity * +price).toLocaleString("en-IN")} before charges`
              : "Execution price determined in the market; review current price in Kite"}
          </p>
          <form
            action="https://kite.zerodha.com/connect/basket"
            method="post"
            target="_blank"
            rel="noopener noreferrer"
          >
            <input type="hidden" name="api_key" value={apiKey.trim()} />
            <input type="hidden" name="data" value={JSON.stringify(basket)} />
            <button className="execute" type="submit">
              Continue to Kite for final review <ExternalLink size={15} />
            </button>
          </form>
          <small>
            Opening Kite does not prove acceptance or execution. Check the
            order’s final status in Kite.
          </small>
        </div>
      )}
    </section>
  );
}
