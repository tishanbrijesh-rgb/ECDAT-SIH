// Application shell and navigation for the ECDAT assurance console.
import { lazy, Suspense } from "react";
import { NavLink, Route, Routes } from "react-router-dom";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const AssetDetail = lazy(() => import("./pages/AssetDetail"));
const ScanPage = lazy(() => import("./pages/ScanPage"));
const AssetsPage = lazy(() => import("./pages/AssetsPage"));

export default function App() {
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
          <NavLink to="/scan">New scan</NavLink>
        </nav>
        <span className="privacy-chip">Local & explainable</span>
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
