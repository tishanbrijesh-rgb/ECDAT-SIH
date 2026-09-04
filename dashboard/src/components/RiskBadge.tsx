interface Props {
  label: string;
  score?: number;
}

const CLASS: Record<string, string> = {
  CRITICAL: "risk-critical",
  HIGH: "risk-high",
  MEDIUM: "risk-medium",
  LOW: "risk-low",
};

export const RiskBadge: React.FC<Props> = ({ label, score }) => {
  const cls = CLASS[label] || "";
  return (
    <span
      className={`risk-badge ${cls}`}
      title={score != null ? `Priority score: ${score}` : undefined}
    >
      <span className="dot" />
      {label}
      {score != null ? ` (${score})` : ""}
    </span>
  );
};
