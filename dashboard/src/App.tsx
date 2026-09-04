// Application shell and navigation for the ECDAT assurance console.
import { lazy, Suspense, useState, useEffect } from "react";
import { login, logout, canWrite, SESSION_EXPIRED } from "./api/client";
import { NavLink, Route, Routes } from "react-router-dom";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const AssetDetail = lazy(() => import("./pages/AssetDetail"));
const ScanPage = lazy(() => import("./pages/ScanPage"));
const AssetsPage = lazy(() => import("./pages/AssetsPage"));

export default function App() {
  const [signedIn, setSignedIn] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const expired = () => {
      setSignedIn(false);
      setError("Your session expired. Please sign in again.");
    };
    window.addEventListener(SESSION_EXPIRED, expired);
    return () => window.removeEventListener(SESSION_EXPIRED, expired);
  }, []);
  if (!signedIn)
    return (
      <div className="login-shell">
        <div className="login-card">
          <div className="brand-row">
            <div className="brand-mark">E</div>
            <div>
              <div className="brand-text">ECDAT</div>
              <div className="brand-sub">Discovery Assurance</div>
            </div>
          </div>
          <h1>Sign in</h1>
          <p>
            Authenticated access to the cryptographic inventory and discovery-assurance console.
          </p>
          {error && (
            <div className="login-error" role="alert">
              {error}
            </div>
          )}
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const data = new FormData(form);
              setBusy(true);
              setError("");
              try {
                await login(String(data.get("username")), String(data.get("password")));
                form.reset();
                setSignedIn(true);
              } catch {
                setError(
                  "Invalid credentials. Check username, password, and server configuration.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              <span>Username</span>
              <input name="username" autoComplete="username" required placeholder="e.g. analyst" />
            </label>
            <label>
              <span>Password</span>
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                placeholder="Enter your password"
              />
            </label>
            <button type="submit" className="button" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <div className="login-hint">
            <strong>Administrator-provisioned access</strong>
            <br />
            Use your configured account. There are no default passwords.
          </div>
        </div>
        <div className="login-footer">
          <span className="shield">&#128737;</span> ECDAT &middot; SIH26164 &middot; Local &amp;
          explainable
        </div>
      </div>
    );
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand" to="/">
          <span className="brand-mark">E</span>
          <span>
            ECDAT<small>Discovery Assurance</small>
          </span>
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Overview
          </NavLink>
          <NavLink to="/assets">Inventory</NavLink>
          {canWrite() && <NavLink to="/scan">New scan</NavLink>}
        </nav>
        <span className="privacy-chip">Local & explainable</span>
        <button
          onClick={() => {
            logout();
            setSignedIn(false);
          }}
        >
          Sign out
        </button>
      </header>
      <main>
        <Suspense
          fallback={
            <div className="state">
              <span className="spinner" />
              <h1>Loading ECDAT</h1>
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/assets" element={<AssetsPage />} />
            <Route path="/assets/:id" element={<AssetDetail />} />
            <Route path="/scan" element={<ScanPage />} />
          </Routes>
        </Suspense>
      </main>
      <footer>ECDAT · SIH26164 · Evidence-backed cryptographic discovery assurance</footer>
    </div>
  );
}
