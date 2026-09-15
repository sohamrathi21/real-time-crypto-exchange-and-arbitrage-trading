import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
const tooltip = {
  background: "var(--panel)",
  border: "1px solid #313941",
  borderRadius: 8,
  color: "var(--text)",
  fontSize: 12,
};
export function StreamChart({
  data,
  field = "edge",
  color = "#dcb865",
  height = 180,
}: {
  data: object[];
  field?: string;
  color?: string;
  height?: number;
}) {
  return (
    <div style={{ height, width: "100%", minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 15, right: 6, bottom: 0, left: 4 }}
        >
          <defs>
            <linearGradient id={`fill-${field}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.22} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="var(--line)"
            vertical={false}
            strokeDasharray="3 4"
          />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(v) =>
              new Date(v).toLocaleTimeString("en-GB", {
                timeZone: "Asia/Kolkata",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })
            }
            stroke="#66717c"
            fontSize={10}
            minTickGap={50}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            width={65}
            domain={field === "price" ? ["auto", "auto"] : undefined}
            stroke="#66717c"
            fontSize={10}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) =>
              Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 })
            }
          />
          <Tooltip
            contentStyle={tooltip}
            labelFormatter={(v) =>
              new Date(Number(v)).toLocaleTimeString("en-GB", {
                timeZone: "Asia/Kolkata",
                hour12: false,
              }) + " IST"
            }
            formatter={(v) => Number(v).toFixed(4)}
          />
          <Area
            type="monotone"
            dataKey={field}
            stroke={color}
            fill={`url(#fill-${field})`}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Bars({
  data,
  field = "value",
  color = "#6acbb2",
}: {
  data: object[];
  field?: string;
  color?: string;
}) {
  return (
    <div style={{ height: 180, minWidth: 0 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: -20 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="name" stroke="#66717c" fontSize={10} />
          <YAxis
            width={65}
            domain={field === "price" ? ["auto", "auto"] : undefined}
            stroke="#66717c"
            fontSize={10}
          />
          <Tooltip contentStyle={tooltip} />
          <Bar dataKey={field} fill={color} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
