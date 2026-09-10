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
import { NavLink, Route, Routes, useSearchParams, useLocation } from "react-router-dom";
import { MotionConfig, AnimatePresence, motion } from "framer-motion";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ToastProvider, useToast } from "./components/Toast";
import { ConfirmDialog } from "./components/ConfirmDialog";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";

// ── Page transition configuration ──────────────────────────────
const pageVariants = {
  initial: { opacity: 0, y: 12, scale: 0.995 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: -8, scale: 0.995 },
};

const pageTransition = {
  duration: 0.22,
  ease: [0.25, 0.1, 0.25, 1],
};

function PageTransition({ children, routeKey }: { children: React.ReactNode; routeKey: string }) {
  return (
    <motion.div
      key={routeKey}
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={pageTransition}
    >
      {children}
    </motion.div>
  );
}

const Dashboard = lazy(() => import("./pages/Dashboard"));
const AssetDetail = lazy(() => import("./pages/AssetDetail"));
const ScanPage = lazy(() => import("./pages/ScanPage"));
const AssetsPage = lazy(() => import("./pages/AssetsPage"));
const RiskReportPage = lazy(() => import("./pages/RiskReport"));
const CbomPage = lazy(() => import("./pages/CbomPage"));
const ScanDetailPage = lazy(() => import("./pages/ScanDetailPage"));

type Theme = "light" | "dark";

function preferredTheme(): Theme {
  const applied = document.documentElement.getAttribute("data-theme");
  if (applied === "light" || applied === "dark") return applied;
  const saved = localStorage.getItem("ecdat-theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function ThemeIcon({ theme }: { theme: Theme }) {
  return theme === "dark" ? (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.5 15.3A8.5 8.5 0 1 1 8.7 3.5a7 7 0 0 0 11.8 11.8Z" />
    </svg>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(preferredTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

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
      <ThemeIcon theme={theme} />
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
  const location = useLocation();

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
          <img className="brand-mark" src="/ecdat-logo.svg" alt="" aria-hidden="true" />
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
        <button
          className="button secondary"
          onClick={() => setConfirmLogout(true)}
          aria-label="Sign out"
        >
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
            <AnimatePresence mode="wait">
              <Routes location={location} key={location.pathname + location.search}>
                <Route
                  path="/"
                  element={
                    <PageTransition routeKey="dashboard">
                      <Dashboard />
                    </PageTransition>
                  }
                />
                <Route
                  path="/assets"
                  element={
                    <PageTransition routeKey="assets">
                      <AssetsPage />
                    </PageTransition>
                  }
                />
                <Route
                  path="/assets/:id"
                  element={
                    <PageTransition routeKey="asset-detail">
                      <AssetDetail />
                    </PageTransition>
                  }
                />
                <Route
                  path="/scan"
                  element={
                    <PageTransition routeKey="scan">
                      <ScanPage />
                    </PageTransition>
                  }
                />
                <Route
                  path="/reports"
                  element={
                    <PageTransition routeKey="reports">
                      <RiskReportPage />
                    </PageTransition>
                  }
                />
                <Route
                  path="/cbom"
                  element={
                    <PageTransition routeKey="cbom">
                      <CbomPage />
                    </PageTransition>
                  }
                />
                <Route
                  path="/scans/:id"
                  element={
                    <PageTransition routeKey="scan-detail">
                      <ScanDetailPage />
                    </PageTransition>
                  }
                />
                <Route
                  path="*"
                  element={
                    <PageTransition routeKey="not-found">
                      <NotFound />
                    </PageTransition>
                  }
                />
              </Routes>
            </AnimatePresence>
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
