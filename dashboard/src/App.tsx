// Application shell and navigation for the ECDAT assurance console.
import { lazy, Suspense, useState, useEffect, useRef, useCallback } from "react";
import {
  logout,
  canWrite,
  getInitialSessionExpiry,
  hasSession,
  restoreSession,
  SESSION_EXPIRED,
} from "./api/client";
import { NavLink, Route, Routes, useSearchParams } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ToastProvider, useToast } from "./components/Toast";
import { ConfirmDialog } from "./components/ConfirmDialog";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const AssetDetail = lazy(() => import("./pages/AssetDetail"));
const ScanPage = lazy(() => import("./pages/ScanPage"));
const AssetsPage = lazy(() => import("./pages/AssetsPage"));
const RiskReportPage = lazy(() => import("./pages/RiskReport"));
const CbomPage = lazy(() => import("./pages/CbomPage"));
const ScanDetailPage = lazy(() => import("./pages/ScanDetailPage"));

function ThemeToggle() {
  const [theme, setTheme] = useState(() =>
    typeof window !== "undefined"
      ? document.documentElement.getAttribute("data-theme") || "light"
      : "light",
  );

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("ecdat-theme", next);
      return next;
    });
  }, []);

  return (
    <button
      className="theme-toggle"
      onClick={toggle}
      title={theme === "dark" ? "Light mode" : "Dark mode"}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    >
      <span aria-hidden="true">{theme === "dark" ? "☀" : "☽"}</span>
    </button>
  );
}

function AppInner() {
  const [authState, setAuthState] = useState<"checking" | "signed-in" | "signed-out">(() =>
    hasSession() ? "checking" : "signed-out",
  );
  const [loginMessage, setLoginMessage] = useState(() => getInitialSessionExpiry());
  const [confirmLogout, setConfirmLogout] = useState(false);
  const { toast } = useToast();
  const mainRef = useRef<HTMLElement>(null);
  const [navParams] = useSearchParams();
  const rawNavScanId = navParams.get("scan_id");
  const scanQuery = rawNavScanId && /^\d+$/.test(rawNavScanId) ? `?scan_id=${rawNavScanId}` : "";

  // Focus main content after sign-in so screen readers announce the page.
  useEffect(() => {
    if (authState === "signed-in") {
      mainRef.current?.focus();
    }
  }, [authState]);

  useEffect(() => {
    const expired = (event: Event) => {
      setLoginMessage(
        (event as CustomEvent<string>).detail || "Your session expired. Please sign in again.",
      );
      setAuthState("signed-out");
    };
    window.addEventListener(SESSION_EXPIRED, expired);
    return () => window.removeEventListener(SESSION_EXPIRED, expired);
  }, []);

  useEffect(() => {
    if (authState !== "checking") return;
    let active = true;
    void restoreSession().then((restored) => {
      if (active) setAuthState(restored ? "signed-in" : "signed-out");
    });
    return () => {
      active = false;
    };
  }, [authState]);

  useEffect(() => {
    const saved = localStorage.getItem("ecdat-theme");
    if (saved) {
      document.documentElement.setAttribute("data-theme", saved);
    } else if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
      document.documentElement.setAttribute("data-theme", "dark");
    }
  }, []);

  if (authState === "checking") {
    return (
      <div className="state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <h1>Restoring your session</h1>
      </div>
    );
  }

  if (authState === "signed-out")
    return (
      <Login
        message={loginMessage}
        onSuccess={() => {
          toast("Welcome back", "success");
          setLoginMessage("");
          setAuthState("signed-in");
        }}
      />
    );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="topbar">
        <NavLink className="brand" to="/">
          <span className="brand-mark">E</span>
          <span>
            ECDAT<small>Discovery Assurance</small>
          </span>
        </NavLink>
        <nav aria-label="Main navigation">
          <NavLink to={`/${scanQuery}`} end>
            Overview
          </NavLink>
          <NavLink to={`/assets${scanQuery}`}>Inventory</NavLink>
          {canWrite() && <NavLink to="/scan">New scan</NavLink>}
          <NavLink to={`/reports${scanQuery}`}>Reports</NavLink>
          <NavLink to={`/cbom${scanQuery}`}>CBOM</NavLink>
        </nav>
        <span className="privacy-chip">Local & explainable</span>
        <ThemeToggle />
        <button onClick={() => setConfirmLogout(true)} aria-label="Sign out">
          Sign out
        </button>
      </header>
      <main id="main-content" ref={mainRef} tabIndex={-1}>
        <Suspense
          fallback={
            <div className="state">
              <span className="spinner" />
              <h1>Loading ECDAT</h1>
            </div>
          }
        >
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/assets" element={<AssetsPage />} />
              <Route path="/assets/:id" element={<AssetDetail />} />
              <Route path="/scan" element={<ScanPage />} />
              <Route path="/reports" element={<RiskReportPage />} />
              <Route path="/cbom" element={<CbomPage />} />
              <Route path="/scans/:id" element={<ScanDetailPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </ErrorBoundary>
        </Suspense>
      </main>
      <footer>ECDAT · SIH26164 · Evidence-backed cryptographic discovery assurance</footer>
      <ConfirmDialog
        open={confirmLogout}
        title="Sign out?"
        message="Your session will be cleared. You will need to sign in again to access the console."
        confirmLabel="Sign out"
        onConfirm={() => {
          logout();
          setLoginMessage("");
          setAuthState("signed-out");
          setConfirmLogout(false);
        }}
        onCancel={() => setConfirmLogout(false)}
      />
    </div>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <ToastProvider>
        <AppInner />
      </ToastProvider>
    </MotionConfig>
  );
}
