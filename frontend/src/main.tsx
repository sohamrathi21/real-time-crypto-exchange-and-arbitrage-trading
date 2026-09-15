import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { authClient } from "./auth";
import "./styles.css";
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  render() {
    return this.state.error ? (
      <main className="loading">
        <h1>Terminal needs to reload</h1>
        <p>An unexpected display error occurred.</p>
        <button onClick={() => location.reload()}>Reload terminal</button>
      </main>
    ) : (
      this.props.children
    );
  }
}
// Start each document load at Home; in-app hash navigation remains available.
async function start() {
const startUrl = new URL(window.location.href);
// Let the auth client process confirmation/recovery before resetting navigation.
if (authClient && (startUrl.searchParams.has('code') || startUrl.hash.includes('access_token='))) {
  await authClient.auth.initialize();
  startUrl.searchParams.delete('code');
}
startUrl.hash = "Home";
window.history.replaceState(window.history.state, "", startUrl);

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);

}
void start();
