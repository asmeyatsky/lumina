import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

interface TrendSeries {
  dataKey: string;
  name: string;
  color: string;
  strokeDasharray?: string;
}

interface TrendChartProps {
  data: Record<string, unknown>[];
  series: TrendSeries[];
  xAxisKey?: string;
  xAxisFormatter?: (value: string) => string;
  yAxisDomain?: [number | string, number | string];
  height?: number;
  showLegend?: boolean;
  showGrid?: boolean;
  className?: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-card border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs text-gray-500 mb-1.5">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-gray-400">{entry.name}:</span>
          <span className="font-medium text-gray-100">
            {typeof entry.value === "number" ? entry.value.toFixed(1) : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function TrendChart({
  data,
  series,
  xAxisKey = "timestamp",
  xAxisFormatter,
  yAxisDomain,
  height = 300,
  showLegend = true,
  showGrid = true,
  className = "",
}: TrendChartProps) {
  const formatXAxis = xAxisFormatter || ((value: string) => {
    try {
      const date = new Date(value);
      return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
      return value;
    }
  });

  return (
    <div className={`w-full ${className}`} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          {showGrid && (
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.04)"
              vertical={false}
            />
          )}
          <XAxis
            dataKey={xAxisKey}
            tickFormatter={formatXAxis}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
            tickLine={false}
          />
          <YAxis
            domain={yAxisDomain}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} />
          {showLegend && (
            <Legend
              wrapperStyle={{ fontSize: 12, color: "#9ca3af" }}
              iconType="circle"
              iconSize={8}
            />
          )}
          {series.map((s) => (
            <Line
              key={s.dataKey}
              type="monotone"
              dataKey={s.dataKey}
              name={s.name}
              stroke={s.color}
              strokeWidth={2}
              strokeDasharray={s.strokeDasharray}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
