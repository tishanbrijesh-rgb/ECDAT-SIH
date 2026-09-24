// MetricCard — a reusable stat tile for the dashboard.
// Renders a label, animated numeric value, and optional trend indicator.
// Uses CSS custom properties for all styling (see primitives.css .stat-*).
import { memo } from "react";

interface MetricCardProps {
  label: string;
  value: number | string;
  suffix?: string;
  tone?: "default" | "teal" | "amber" | "red" | "forest";
  href?: string;
  onClick?: () => void;
  /** ARIA live-region value for screen reader announcements. */
  "aria-valuenow"?: number;
  /** Minimum bound for ARIA value (defaults to 0). */
  "aria-valuemin"?: number;
  /** Maximum bound for ARIA value (defaults to 100). */
  "aria-valuemax"?: number;
}

const TONE_CLASS: Record<string, string> = {
  default: "stat-tone-default",
  teal: "stat-tone-teal",
  amber: "stat-tone-amber",
  red: "stat-tone-red",
  forest: "stat-tone-forest",
};

export const MetricCard = memo(function MetricCard({
  label,
  value,
  suffix = "",
  tone = "default",
  href,
  onClick,
  "aria-valuenow": ariaValueNow,
  "aria-valuemin": ariaValueMin = 0,
  "aria-valuemax": ariaValueMax = 100,
}: MetricCardProps) {
  const cls = `stat ${TONE_CLASS[tone]}`;
  const isNumeric = typeof value === "number";
  const content = (
    <>
      <strong className="stat-value">
        {value}
        {suffix}
      </strong>
      <span className="stat-label">{label}</span>
    </>
  );

  if (href) {
    return (
      <a
        href={href}
        className={cls}
        onClick={onClick}
        role="status"
        aria-valuenow={isNumeric ? (ariaValueNow ?? value) : undefined}
        aria-valuemin={isNumeric ? ariaValueMin : undefined}
        aria-valuemax={isNumeric ? ariaValueMax : undefined}
      >
        {content}
      </a>
    );
  }

  if (onClick) {
    return (
      <button
        type="button"
        className={cls}
        onClick={onClick}
        aria-valuenow={isNumeric ? (ariaValueNow ?? value) : undefined}
        aria-valuemin={isNumeric ? ariaValueMin : undefined}
        aria-valuemax={isNumeric ? ariaValueMax : undefined}
      >
        {content}
      </button>
    );
  }

  return (
    <div
      className={cls}
      role="status"
      aria-valuenow={isNumeric ? (ariaValueNow ?? value) : undefined}
      aria-valuemin={isNumeric ? ariaValueMin : undefined}
      aria-valuemax={isNumeric ? ariaValueMax : undefined}
    >
      {content}
    </div>
  );
});
