// Toast notification context and hook for the ECDAT dashboard.
// Supports pause-on-hover and a shrinking progress bar.
import React, {
  createContext,
  useEffect,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";

export type ToastVariant = "info" | "success" | "error" | "warning";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
  expiresAt: number;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warn: (message: string) => void;
}

const TOAST_DURATION = 4000;

const ToastContext = createContext<ToastContextValue>({
  toast: () => {},
  success: () => {},
  error: () => {},
  warn: () => {},
});

let nextId = 0;

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      timers.current.clear();
    },
    [],
  );

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const scheduleRemoval = useCallback(
    (id: number, expiresAt: number) => {
      const remaining = expiresAt - Date.now();
      if (remaining <= 0) return remove(id);
      const timer = setTimeout(() => remove(id), remaining);
      timers.current.set(id, timer);
    },
    [remove],
  );

  const add = useCallback(
    (message: string, variant: ToastVariant = "info") => {
      const id = ++nextId;
      const expiresAt = Date.now() + TOAST_DURATION;
      setToasts((prev) => [...prev, { id, message, variant, expiresAt }]);
      scheduleRemoval(id, expiresAt);
      return id;
    },
    [scheduleRemoval],
  );

  const pause = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    // Extend expiry so the progress bar keeps shrinking visually
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, expiresAt: t.expiresAt + TOAST_DURATION } : t)),
    );
  }, []);

  const resume = useCallback(
    (id: number) => {
      setToasts((prev) => {
        const t = prev.find((x) => x.id === id);
        if (!t) return prev;
        const remaining = t.expiresAt - Date.now();
        if (remaining <= 0) {
          remove(id);
          return prev;
        }
        scheduleRemoval(id, t.expiresAt);
        return prev;
      });
    },
    [remove, scheduleRemoval],
  );

  return (
    <ToastContext.Provider
      value={{
        toast: add,
        success: (m) => add(m, "success"),
        error: (m) => add(m, "error"),
        warn: (m) => add(m, "warning"),
      }}
    >
      {children}
      <div className="toast-container" aria-label="Notifications">
        {toasts.map((t) => {
          const now = Date.now();
          const remaining = Math.max(0, t.expiresAt - now);
          const pct = (remaining / TOAST_DURATION) * 100;
          return (
            <div
              key={t.id}
              className={`toast toast-${t.variant}`}
              role={t.variant === "error" ? "alert" : "status"}
              aria-live={t.variant === "error" ? "assertive" : "polite"}
              aria-atomic="true"
              onMouseEnter={() => pause(t.id)}
              onMouseLeave={() => resume(t.id)}
            >
              <span className="toast-icon" aria-hidden="true">
                {t.variant === "success" && "✓"}
                {t.variant === "error" && "✗"}
                {t.variant === "warning" && "⚠"}
                {t.variant === "info" && "ℹ"}
              </span>
              <span className="toast-msg">{t.message}</span>
              <button
                className="toast-close"
                onClick={() => remove(t.id)}
                aria-label={`Dismiss ${t.variant} notification`}
              >
                &times;
              </button>
              <div className="toast-progress" style={{ width: `${pct}%` }} />
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => useContext(ToastContext);
