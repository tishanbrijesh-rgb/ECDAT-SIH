// Login page — ECDAT design system.
import { useEffect, useId, useState, type FormEvent } from "react";
import { ApiError, enterPublicDemo, login } from "../api/client";

export default function Login({
  onSuccess,
  message = "",
}: {
  onSuccess: (mode?: "demo" | "account") => void;
  message?: string;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(message);
  const [busy, setBusy] = useState(false);

  // Login page must always render in light mode — cryptographic assurance identity
  useEffect(() => {
    const root = document.documentElement;
    const prev = root.getAttribute("data-theme");
    root.setAttribute("data-theme", "light");
    return () => {
      if (prev === null) root.removeAttribute("data-theme");
      else root.setAttribute("data-theme", prev);
    };
  }, []);

  useEffect(() => setError(message), [message]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      onSuccess("account");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Invalid username or password."
          : err instanceof ApiError && err.status === 429
            ? "Too many sign-in attempts. Please try again later."
            : "Unable to sign in. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const openDemo = async () => {
    setBusy(true);
    setError("");
    try {
      if (!await enterPublicDemo()) {
        setError("SIH Demo is unavailable. Please try again shortly.");
        return;
      }
      onSuccess("demo");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <main className="login-shell" id="main-content" tabIndex={-1}>
        <aside className="login-context" aria-label="About ECDAT">
          <div className="login-identity">
            <img className="brand-mark" src="/ecdat-logo.svg" alt="" aria-hidden="true" />
            <div>
              <div className="login-identity-name">ECDAT</div>
              <div className="login-identity-subtitle">Discovery Assurance</div>
            </div>
          </div>
          <div className="login-panel-body">
            <p className="login-context-title">Enterprise Cryptographic Discovery &amp; Analysis Tool</p>
            <p>
              Correlate source, dependency, certificate, and rule evidence into an inventory your
              security team can defend.
            </p>
          </div>
        </aside>
        <section className="login-panel--form" aria-labelledby="login-heading">
          <div className="login-card">
            <h1 id="login-heading" className="login-card-title">Explore ECDAT</h1>
            <p className="login-card-desc">
              Open the SIH demo to explore results. Sign in below when you need to run a scan.
            </p>

            {error && (
              <div className="login-error" id="login-error" role="alert">
                {error}
              </div>
            )}

            <button type="button" className="button wide login-submit" onClick={openDemo} disabled={busy}>
              {busy ? "Opening SIH Demo…" : "SIH Demo — no password"}
            </button>
            <p className="login-card-desc login-choice-note">View the dashboard, inventory, reports, and completed scans.</p>

            <h2 className="login-section-title">Scanner sign-in</h2>
            <form onSubmit={submit} aria-busy={busy} className="login-form">
              <LoginField
                label="Username"
                value={username}
                onChange={setUsername}
                autoComplete="username"
                invalid={Boolean(error)}
                describedBy={error ? "login-error" : undefined}
              />

              <LoginField
                label="Password"
                value={password}
                onChange={setPassword}
                type="password"
                autoComplete="current-password"
                invalid={Boolean(error)}
                describedBy={error ? "login-error" : undefined}
              />

              <button
                type="submit"
                className="button wide login-submit"
                disabled={busy || !username || !password}
              >
                {busy && <span className="spinner login-spinner" aria-hidden="true" />}
                {busy ? "Signing in…" : "Sign in"}
              </button>
            </form>

            <div className="login-hint" role="note">
              <strong>Scanner or administrator access</strong>
              <span>Use your configured account. There are no default passwords.</span>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}

function LoginField({
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  invalid = false,
  describedBy,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoComplete?: string;
  invalid?: boolean;
  describedBy?: string;
}) {
  const inputId = useId();

  return (
    <div className="float-field">
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        name={label.toLowerCase()}
        type={type}
        value={value}
        autoComplete={autoComplete}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        required
        placeholder=" "
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
