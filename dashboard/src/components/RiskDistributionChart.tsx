import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function RiskDistributionChart({
  data,
}: {
  data: Array<{ label: string; count: number }>;
}) {
  return (
    <ResponsiveContainer width="100%" height={270}>
      <BarChart data={data} aria-label="Risk distribution by priority level">
        <title>Cryptographic risk distribution</title>
        <desc>
          Bar chart showing the count of assets at each risk level: Critical, High, Medium, Low.
        </desc>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={{ stroke: "var(--line)" }}
          tick={{ fill: "var(--muted)", fontSize: 12 }}
        />
        <YAxis
          allowDecimals={false}
          tickLine={false}
          axisLine={{ stroke: "var(--line)" }}
          tick={{ fill: "var(--muted)", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            borderRadius: 10,
            border: "1px solid var(--line)",
            background: "var(--panel)",
            color: "var(--text)",
            boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
            fontSize: 13,
          }}
          cursor={{ fill: "var(--indigo)", fillOpacity: 0.06 }}
        />
        <Bar dataKey="count" fill="var(--indigo)" radius={[8, 8, 0, 0]} maxBarSize={56} />
      </BarChart>
    </ResponsiveContainer>
  );
}
