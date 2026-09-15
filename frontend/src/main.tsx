import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
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
const startUrl = new URL(window.location.href);
startUrl.hash = "Home";
window.history.replaceState(window.history.state, "", startUrl);

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
