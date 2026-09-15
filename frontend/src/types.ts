/// <reference types="vite/client" />
export type Opportunity = {
  id: string;
  symbol: string;
  type: string;
  buy_venue: string;
  sell_venue: string;
  source: string;
  quote: string;
  buy_price: number;
  sell_price: number;
  trade_quantity: number;
  gross_profit: number;
  buy_fee: number;
  sell_fee: number;
  estimated_slippage: number;
  price_impact: number;
  slippage_percent: number;
  network_cost: number;
  other_costs: number;
  net_profit: number;
  gross_spread_percent: number;
  net_edge_percent: number;
  capital_required: number;
  roi: number;
  execution_latency: number;
  liquidity_score: number;
  available_liquidity: number;
  confidence_score: number;
  confidence_factors: Record<string, number>;
  timestamp: number;
  first_seen: number;
  price_age_ms: number;
  path: string[];
  legs: {
    symbol: string;
    side: string;
    input: number;
    output: number;
    fee: number;
    fee_currency: string;
    vwap: number;
  }[];
  assumptions: string[];
};
export type Price = {
  exchange: string;
  symbol: string;
  base: string;
  quote: string;
  price: number;
  bid: number;
  ask: number;
  spread_percent: number;
  depth_notional: number;
  source: string;
  asset_class: string;
  timestamp: number;
  stale: boolean;
};
export type Trade = Opportunity & {
  timestamp: number;
  status: string;
  fees: number;
};
export type Portfolio = {
  starting_capital: number;
  available_capital: number;
  realized_pnl: number;
  unrealized_pnl: number;
  win_rate: number;
  number_of_trades: number;
  average_return: number;
  maximum_drawdown: number;
  quote: string;
};
export type Snapshot = {
  timestamp: number;
  mode: string;
  opportunities: Opportunity[];
  prices: Price[];
  venues: Record<
    string,
    { state: string; source: string; latency_ms?: number; error?: string }
  >;
  portfolio: Portfolio;
  trades: Trade[];
  alerts: { id: string; timestamp: number; kind: string; message: string }[];
  history: { timestamp: number; edge: number; count: number; pnl: number }[];
  detection_ms: number;
  end_to_end_ms: number;
  rejected: number;
  redis: string;
  database: string;
  settings: Record<string, unknown>;
};
export type Book = {
  bids: { price: number; quantity: number }[];
  asks: { price: number; quantity: number }[];
};
