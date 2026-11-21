import { useEffect, useState } from "react";
import { HashRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import ChatPage from "./pages/ChatPage";
import DashboardPage from "./pages/DashboardPage";
import DocumentsPage from "./pages/DocumentsPage";
import GraphPage from "./pages/GraphPage";
import CoursePicker from "./components/CoursePicker";

const NAV = [
  { to: "/chat", label: "Learning chat", icon: "💬" },
  { to: "/graph", label: "Knowledge graph", icon: "🕸️" },
  { to: "/documents", label: "Documents", icon: "📄" },
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
];

/** Pings /health so a stopped backend is visible before the first 500. */
function BackendStatus() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        await api.health();
        if (!cancelled) setOk(true);
      } catch {
        if (!cancelled) setOk(false);
      }
    }
    void check();
    const timer = setInterval(() => void check(), 20000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);
  const hint =
    ok === null
      ? "Checking…"
      : ok
        ? "Connected to server"
        : "Server offline — Start the server: python -m uvicorn app.main:app";
  return (
    <div className={`backend-status${ok === false ? " down" : ""}`} title={hint}>
      <span className="status-dot" />
      {ok === null ? "Checking" : ok ? "Online" : "Offline"}
    </div>
  );
}

export default function App() {
  return (
    // HashRouter: page paths (/chat, /graph, /documents) must not collide with
    // the API routes of the same names — with hash URLs the server only ever
    // sees "/", and hard refreshes still work.
    <HashRouter>
      <div className="app">
        <aside className="sidebar">
          <h1 className="brand">AI Learning Assistant</h1>
          <CoursePicker />
          <nav>
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
              >
                <span className="nav-icon">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <BackendStatus />
        </aside>
        <main className="content">
          <Routes>
            <Route path="/" element={<Navigate to="/documents" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/graph" element={<GraphPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}
