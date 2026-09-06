// Animated login page with framer-motion entrance, floating labels, and brand animation.
import { useEffect, useId, useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { login } from "../api/client";

const ORB_COUNT = 5;

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
    } catch {
      setError("Invalid username or password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-shell">
      {/* Animated background orbs */}
      {Array.from({ length: ORB_COUNT }).map((_, i) => (
        <motion.div
          key={i}
          className={`login-orb login-orb--${i + 1}`}
          animate={{
            x: [0, 30 + i * 15, -20 + i * 10, 0],
            y: [0, -25 - i * 12, 15 + i * 8, 0],
            scale: [1, 1.15 + i * 0.05, 0.9, 1],
          }}
          transition={{
            duration: 8 + i * 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}

      <motion.div
        className="login-card"
        aria-labelledby="login-heading"
        initial={{ opacity: 0, y: 40, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Brand */}
        <motion.div
          className="login-brand"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          <motion.div
            className="brand-mark"
            aria-hidden="true"
            animate={{
              boxShadow: [
                "0 4px 12px rgba(66,87,214,0.3)",
                "0 4px 20px rgba(66,87,214,0.5)",
                "0 4px 12px rgba(66,87,214,0.3)",
              ],
            }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          >
            E
          </motion.div>
          <div>
            <div className="brand-text">ECDAT</div>
            <div className="brand-sub">Discovery Assurance</div>
          </div>
        </motion.div>

        <motion.h1
          id="login-heading"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          Sign in
        </motion.h1>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}>
          Authenticated access to the cryptographic inventory and discovery-assurance console.
        </motion.p>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div
              className="login-error"
              id="login-error"
              role="alert"
              initial={{ opacity: 0, y: -8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        <form onSubmit={submit} aria-busy={busy}>
          <motion.div
            className="field"
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 }}
          >
            <FloatingLabel
              label="Username"
              value={username}
              onChange={setUsername}
              autoComplete="username"
              autoFocus
              invalid={Boolean(error)}
              describedBy={error ? "login-error" : undefined}
            />
          </motion.div>

          <motion.div
            className="field"
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.45 }}
          >
            <FloatingLabel
              label="Password"
              value={password}
              onChange={setPassword}
              type="password"
              autoComplete="current-password"
              invalid={Boolean(error)}
              describedBy={error ? "login-error" : undefined}
            />
          </motion.div>

          <motion.button
            type="submit"
            className="button wide login-submit"
            disabled={busy || !username || !password}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            whileHover={{ scale: busy ? 1 : 1.02 }}
            whileTap={{ scale: busy ? 1 : 0.98 }}
          >
            {busy && <span className="spinner login-spinner" aria-hidden="true" />}
            {busy ? "Signing in…" : "Sign in"}
          </motion.button>
        </form>

        <motion.div
          className="login-hint"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
        >
          <strong>Administrator-provisioned access</strong>
          <br />
          Use your configured account. There are no default passwords.
        </motion.div>
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

/* ── Floating label input ─────────────────────────────── */
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
