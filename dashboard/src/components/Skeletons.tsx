// Loading skeleton components for the ECDAT dashboard.
import { memo } from "react";

export const SkeletonCard = memo(function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skeleton skeleton-circle" />
      <div className="skeleton skeleton-line medium" />
      <div className="skeleton skeleton-line short" />
    </div>
  );
});

export const SkeletonStat = memo(function SkeletonStat() {
  return (
    <div className="skeleton-card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
      <div className="skeleton skeleton-circle" style={{ width: 40, height: 40, flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div className="skeleton skeleton-line short" />
        <div className="skeleton skeleton-line medium" style={{ width: "60%" }} />
      </div>
    </div>
  );
});

export const SkeletonTable = memo(function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="panel table-wrap">
      <div style={{ padding: "12px 8px" }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} style={{ display: "flex", gap: 12, marginBottom: 10, alignItems: "center" }}>
            <div className="skeleton skeleton-bar" style={{ width: 40, flexShrink: 0 }} />
            <div className="skeleton skeleton-bar" style={{ width: 180 }} />
            <div className="skeleton skeleton-bar" style={{ width: 100 }} />
            <div className="skeleton skeleton-bar" style={{ width: 60 }} />
            <div className="skeleton skeleton-bar" style={{ width: 80 }} />
          </div>
        ))}
      </div>
    </div>
  );
});

export const SkeletonPanel = memo(function SkeletonPanel() {
  return (
    <div style={{ padding: 24 }}>
      <div className="skeleton skeleton-line medium" />
      <div className="skeleton skeleton-line short" />
      <div className="skeleton skeleton-line" style={{ width: "90%" }} />
      <div className="skeleton skeleton-line" style={{ width: "75%" }} />
      <div style={{ height: 16 }} />
      <div className="skeleton skeleton-line" style={{ width: "85%" }} />
      <div className="skeleton skeleton-line short" />
    </div>
  );
});
