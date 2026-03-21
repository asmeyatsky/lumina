import { useParams } from "react-router-dom";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import PageHeader from "@/components/layout/PageHeader";
import Badge from "@/components/common/Badge";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import DataTable, { type Column } from "@/components/common/DataTable";
import { useRunDetails } from "@/hooks/useApi";

interface RunDetailProps {
  brandId: string;
}

interface CitationRecord {
  id: string;
  engine: string;
  query: string;
  cited: boolean;
  position: number | null;
  context: string;
  sentiment: string;
  [key: string]: unknown;
}

export default function RunDetail({ brandId }: RunDetailProps) {
  const { runId } = useParams<{ runId: string }>();
  const runDetails = useRunDetails(runId || "");

  // Mock citation results
  const citations: CitationRecord[] = [
    { id: "c1", engine: "claude", query: "Best analytics tools", cited: true, position: 2, context: "...considered one of the leading analytics platforms...", sentiment: "positive" },
    { id: "c2", engine: "gpt-4o", query: "Best analytics tools", cited: true, position: 1, context: "...the top choice for enterprise analytics...", sentiment: "positive" },
    { id: "c3", engine: "gemini", query: "Best analytics tools", cited: false, position: null, context: "", sentiment: "neutral" },
    { id: "c4", engine: "perplexity", query: "Best analytics tools", cited: true, position: 3, context: "...frequently mentioned alongside competitors...", sentiment: "neutral" },
    { id: "c5", engine: "claude", query: "Data visualization software", cited: true, position: 1, context: "...widely recognized for data visualization...", sentiment: "positive" },
    { id: "c6", engine: "gpt-4o", query: "Data visualization software", cited: false, position: null, context: "", sentiment: "neutral" },
    { id: "c7", engine: "gemini", query: "Data visualization software", cited: true, position: 4, context: "...also offers visualization capabilities...", sentiment: "neutral" },
    { id: "c8", engine: "perplexity", query: "Data visualization software", cited: true, position: 2, context: "...strong contender in the visualization space...", sentiment: "positive" },
  ];

  const sentimentData = [
    { sentiment: "Positive", count: citations.filter((c) => c.sentiment === "positive").length },
    { sentiment: "Neutral", count: citations.filter((c) => c.sentiment === "neutral").length },
    { sentiment: "Negative", count: citations.filter((c) => c.sentiment === "negative").length },
  ];

  const columns: Column<CitationRecord>[] = [
    {
      key: "engine",
      header: "Engine",
      render: (row) => (
        <span className="text-sm font-medium capitalize text-gray-200">
          {row.engine}
        </span>
      ),
    },
    { key: "query", header: "Query" },
    {
      key: "cited",
      header: "Cited",
      render: (row) => (
        <Badge variant={row.cited ? "success" : "danger"} dot>
          {row.cited ? "Yes" : "No"}
        </Badge>
      ),
    },
    {
      key: "position",
      header: "Position",
      render: (row) => (
        <span className={row.position ? "text-gray-200 font-mono" : "text-gray-600"}>
          {row.position ? `#${row.position}` : "--"}
        </span>
      ),
    },
    {
      key: "sentiment",
      header: "Sentiment",
      render: (row) => (
        <Badge
          variant={
            row.sentiment === "positive"
              ? "success"
              : row.sentiment === "negative"
              ? "danger"
              : "neutral"
          }
        >
          {row.sentiment}
        </Badge>
      ),
    },
  ];

  const status = runDetails.data?.status || "completed";
  const statusVariant =
    status === "completed" ? "success" : status === "running" ? "info" : "warning";

  return (
    <div className="animate-fade-in">
      <PageHeader
        title={`Monitoring Run ${runId || ""}`}
        subtitle="Detailed results from AI engine monitoring"
        actions={
          <Badge variant={statusVariant as "success" | "info" | "warning"} dot>
            {status}
          </Badge>
        }
      />

      {/* Run Metadata */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div className="glass-panel p-4">
          <div className="text-xs text-gray-500 mb-1">Engines</div>
          <div className="text-sm font-medium text-gray-200">4 engines</div>
        </div>
        <div className="glass-panel p-4">
          <div className="text-xs text-gray-500 mb-1">Total Queries</div>
          <div className="text-sm font-medium text-gray-200">{citations.length}</div>
        </div>
        <div className="glass-panel p-4">
          <div className="text-xs text-gray-500 mb-1">Citation Rate</div>
          <div className="text-sm font-medium text-success">
            {((citations.filter((c) => c.cited).length / citations.length) * 100).toFixed(0)}%
          </div>
        </div>
        <div className="glass-panel p-4">
          <div className="text-xs text-gray-500 mb-1">Avg Position</div>
          <div className="text-sm font-medium text-gray-200">
            #{(
              citations
                .filter((c) => c.position)
                .reduce((sum, c) => sum + (c.position || 0), 0) /
              citations.filter((c) => c.position).length
            ).toFixed(1)}
          </div>
        </div>
      </div>

      {/* Sentiment Chart + Citation Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Sentiment Breakdown
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={sentimentData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#6b7280", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis
                type="category"
                dataKey="sentiment"
                tick={{ fill: "#6b7280", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={70}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="bg-card border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl text-sm">
                      <span className="text-gray-200">
                        {payload[0].payload.sentiment}: {payload[0].value}
                      </span>
                    </div>
                  );
                }}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {sentimentData.map((entry, i) => {
                  const colors = ["#22c55e", "#6b7280", "#ef4444"];
                  return (
                    <Bar key={i} dataKey="count" fill={colors[i]} />
                  );
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Citation Highlight Cards */}
        <div className="lg:col-span-2 glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Citation Highlights
          </h2>
          <div className="space-y-3 max-h-[280px] overflow-y-auto pr-2">
            {citations
              .filter((c) => c.cited && c.context)
              .map((c) => (
                <div
                  key={c.id}
                  className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Badge variant="info">{c.engine}</Badge>
                    {c.position && (
                      <span className="text-xs text-gray-500 font-mono">
                        Position #{c.position}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mb-1">{c.query}</p>
                  <p className="text-sm text-gray-300 italic">{c.context}</p>
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* Full Results Table */}
      <div className="glass-panel p-6">
        <h2 className="text-base font-semibold text-gray-200 mb-4">
          Citation Results
        </h2>
        <DataTable
          columns={columns}
          data={citations}
          searchable
          searchPlaceholder="Search queries..."
          pageSize={10}
        />
      </div>
    </div>
  );
}
