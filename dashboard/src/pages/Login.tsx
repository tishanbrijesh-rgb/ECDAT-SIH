// Login page with clean framer-motion entrance and floating labels.
import { useEffect, useId, useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ApiError, login } from "../api/client";

export default function Login({
  onSuccess,
  message = "",
}: {
  onSuccess: () => void;
  message?: string;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(message);
  const [busy, setBusy] = useState(false);

  useEffect(() => setError(message), [message]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      onSuccess();
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

  return (
    <div className="login-shell">
      <motion.div
        className="login-card"
        aria-labelledby="login-heading"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="login-brand">
          <img className="brand-mark" src="/ecdat-logo.svg" alt="" aria-hidden="true" />
          <div>
            <div className="brand-text">ECDAT</div>
            <div className="brand-sub">Discovery Assurance</div>
          </div>
        </div>

        <h1 id="login-heading">Sign in</h1>
        <p>Authenticated access to the cryptographic inventory and discovery-assurance console.</p>

        <AnimatePresence>
          {error && (
            <motion.div
              className="login-error"
              id="login-error"
              role="alert"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        <form onSubmit={submit} aria-busy={busy}>
          <FloatingLabel
            label="Username"
            value={username}
            onChange={setUsername}
            autoComplete="username"
            autoFocus
            invalid={Boolean(error)}
            describedBy={error ? "login-error" : undefined}
          />

          <FloatingLabel
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

        <div className="login-hint">
          <strong>Administrator-provisioned access</strong>
          <br />
          Use your configured account. There are no default passwords.
        </div>
      </motion.div>

      <div className="login-footer">
        <span className="shield" aria-hidden="true">
          &#128737;
        </span>{" "}
        ECDAT &middot; SIH26164 &middot; Local &amp; explainable
      </div>
    </div>
  );
}

function FloatingLabel({
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  autoFocus = false,
  invalid = false,
  describedBy,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoComplete?: string;
  autoFocus?: boolean;
  invalid?: boolean;
  describedBy?: string;
}) {
  const active = value.length > 0;
  const inputId = useId();

  return (
    <div className={`float-field ${active ? "float-field--active" : ""}`}>
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        name={label.toLowerCase()}
        type={type}
        value={value}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        required
        placeholder=" "
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="float-underline" />
    </div>
  );
}
