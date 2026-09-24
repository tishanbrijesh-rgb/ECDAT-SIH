// StatusBadge — a compact status indicator for operational states.
// Leverages existing .status-* CSS rules from components.css.
import { memo } from "react";

type StatusKey = "running" | "ok" | "warn" | "error" | "cancelled" | "timed_out";

interface StatusBadgeProps {
  status: StatusKey;
  label?: string;
  pulse?: boolean;
  size?: "sm" | "md";
}

const STATUS_LABEL: Record<StatusKey, string> = {
  running: "Scanning",
  ok: "Complete",
  warn: "Warning",
  error: "Failed",
  cancelled: "Cancelled",
  timed_out: "Timed out",
};

export const StatusBadge = memo(function StatusBadge({
  status,
  label,
  pulse = false,
  size = "md",
}: StatusBadgeProps) {
  const display = label || STATUS_LABEL[status];
  return (
    <span
      className={`status status-${status} status-badge-${size}${pulse ? " status-pulse" : ""}`}
      title={status}
    >
      <span className="status-dot" />
      {display}
    </span>
  );
});
