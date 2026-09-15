import { useEffect, useState } from "react";
import { CreditCard, ExternalLink, RefreshCw, ShieldCheck } from "lucide-react";
import { request } from "./api";
import { PanelHead } from "./panels";
type BillingState = {
  configured: boolean;
  mode: string;
  status: string;
  has_customer?: boolean;
  cancel_at_period_end?: boolean;
  plan: null | {
    amount: number;
    currency: string;
    interval: string;
    interval_count: number;
    livemode: boolean;
  };
};
function priceLabel(p: NonNullable<BillingState["plan"]>) {
  const formatter = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: p.currency.toUpperCase(),
  });
  const digits = ["isk", "ugx"].includes(p.currency)
    ? 2
    : (formatter.resolvedOptions().maximumFractionDigits ?? 2);
  return formatter.format(p.amount / 10 ** digits);
}
export function Subscription() {
  const [data, setData] = useState<BillingState | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      setData(await request<BillingState>("/billing/status"));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Billing unavailable");
    }
  };
  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 15000);
    return () => clearInterval(id);
  }, []);
  const open = async (path: string) => {
    setBusy(true);
    setError("");
    try {
      const result = await request<{ url: string }>(path, {
        method: "POST",
        body: "{}",
      });
      const u = new URL(result.url);
      if (
        u.protocol !== "https:" ||
        !["checkout.stripe.com", "billing.stripe.com"].includes(u.hostname)
      )
        throw new Error("Unexpected billing destination");
      window.location.assign(u.href);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open Stripe");
      setBusy(false);
    }
  };
  return (
    <section className="panel subscription-panel">
      <PanelHead
        title="ARBITRAGE X subscription"
        sub="Stripe-hosted checkout, invoices and subscription management"
        action={
          <button className="secondary-button" onClick={() => void load()}>
            <RefreshCw size={13} />
            Refresh status
          </button>
        }
      />
      <div className="subscription-grid">
        <article className="subscription-plan">
          <CreditCard size={27} />
          <div className="eyebrow">WORKSPACE SUBSCRIPTION</div>
          <h2>{data?.plan ? priceLabel(data.plan) : "Price not configured"}</h2>
          <p>
            {data?.plan
              ? `Every ${data.plan.interval_count === 1 ? "" : data.plan.interval_count + " "}${data.plan.interval}${data.plan.interval_count > 1 ? "s" : ""} · final taxes and total shown at Checkout`
              : "Your recurring price and billing interval will be read from Stripe."}
          </p>
          <ul>
            <li>Market analysis workspace</li>
            <li>Publisher news and regional views</li>
            <li>Paper-trading tools and reporting</li>
            <li>Automation workspace</li>
          </ul>
          <button
            className="execute"
            disabled={
              !data?.configured ||
              busy ||
              ["active", "trialing", "past_due", "unpaid", "paused"].includes(
                data?.status || "",
              )
            }
            onClick={() => void open("/billing/checkout")}
          >
            {busy
              ? "Opening Stripe…"
              : data?.mode === "test"
                ? "Open test Checkout"
                : "Subscribe with Stripe"}
            <ExternalLink size={14} />
          </button>
          <small>No payment details are entered or stored in this app.</small>
        </article>
        <article className="subscription-state">
          <ShieldCheck size={27} />
          <h3>Subscription status</h3>
          <b className="gold">
            {(data?.status || "loading").replaceAll("_", " ").toUpperCase()}
          </b>
          <p>
            Mode:{" "}
            {data?.mode === "live" ? "LIVE BILLING" : "TEST / NOT CONNECTED"}
          </p>
          {data?.cancel_at_period_end && (
            <p>Cancellation is scheduled at the end of the billing period.</p>
          )}
          <button
            className="secondary-button"
            disabled={!data?.has_customer || busy}
            onClick={() => void open("/billing/portal")}
          >
            Manage billing in Stripe <ExternalLink size={13} />
          </button>
          <p>
            Status changes only after a verified Stripe webhook. A successful
            redirect alone does not activate a subscription.
          </p>
          {!data?.configured && (
            <p>
              Setup required: server-side Stripe secret key, webhook signing
              secret and recurring Price ID. The local preview remains
              available.
            </p>
          )}
          <p>
            Billing is linked to this browser’s local session. Account login and
            cross-device recovery are not yet part of this local preview.
          </p>
        </article>
      </div>
      {error && <p className="error banner">{error}</p>}
    </section>
  );
}
