// Renders a horizontal bar whose width maps confidence (0-1) to 0-100%,
// color-coded: green > 0.8, yellow 0.5-0.8, red < 0.5.
import { memo } from "react";

interface Props {
  confidence: number;
}

export const ConfidenceBar = memo(function ConfidenceBar({ confidence }: Props) {
  const pct = Math.round(confidence * 100);
  const cls = confidence > 0.8 ? "conf-high" : confidence >= 0.5 ? "conf-mid" : "conf-low";

  return (
    <div className={`confidence-bar ${cls}`}>
      <div className="track">
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="pct">{pct}% confidence</span>
    </div>
  );
});
