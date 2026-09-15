import { useEffect, useRef, useState } from "react";
import type { Snapshot } from "./types";
export const API = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");
export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(API + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || "Request failed");
  }
  return res.json();
}
export function useMarket() {
  const [data, setData] = useState<Snapshot | null>(null),
    [connected, setConnected] = useState(false),
    [error, setError] = useState("");
  const latest = useRef(0);
  useEffect(() => {
    let stopped = false,
      socket: WebSocket,
      retry: ReturnType<typeof setTimeout>,
      attempt = 0;
    const accept = (next: Snapshot) => {
      if (next.timestamp >= latest.current) {
        latest.current = next.timestamp;
        setData(next);
        setError("");
      }
    };
    request<Snapshot>("/analytics")
      .then(accept)
      .catch((e) => setError(e.message));
    function connect() {
      const url =
        import.meta.env.VITE_WS_URL ||
        (API.startsWith("http")
          ? API.replace(/^http/, "ws") + "/ws/market"
          : `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/market`);
      socket = new WebSocket(url);
      socket.onopen = () => {
        attempt = 0;
        setConnected(true);
        setError("");
      };
      socket.onmessage = (e) => {
        try {
          const next = JSON.parse(e.data);
          if (next.timestamp) accept(next);
        } catch {
          setError("Malformed stream event ignored");
        }
      };
      socket.onerror = () =>
        setError("Market stream unavailable. Reconnecting…");
      socket.onclose = () => {
        setConnected(false);
        if (!stopped)
          retry = setTimeout(connect, Math.min(15000, 1000 * 2 ** attempt++));
      };
    }
    connect();
    const heartbeat = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send("ping");
        if (Date.now() - latest.current > 15000) socket.close();
      }
    }, 5000);
    return () => {
      stopped = true;
      clearTimeout(retry);
      clearInterval(heartbeat);
      socket?.close();
    };
  }, []);
  return { data, connected, error };
}
export const fmt = (n: number, d = 2) =>
  new Intl.NumberFormat("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  }).format(n);
export const compact = (n: number) =>
  new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n);
export const time = (n: number) =>
  new Date(n).toLocaleTimeString("en-GB", {
    hour12: false,
    timeZone: "Asia/Kolkata",
  });
