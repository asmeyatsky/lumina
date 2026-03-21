import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search as SearchIcon, Code, AlertCircle } from "lucide-react";
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip,
} from "recharts";
import PageHeader from "@/components/layout/PageHeader";
import ScoreGauge from "@/components/common/ScoreGauge";
import Badge from "@/components/common/Badge";
import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import {
  useEntityProfile,
  useKnowledgeGaps,
  useRunGapAnalysis,
  useGenerateJsonLd,
} from "@/hooks/useApi";

interface GraphOverviewProps {
  brandId: string;
}

export default function GraphOverview({ brandId }: GraphOverviewProps) {
  const navigate = useNavigate();
  const entityProfile = useEntityProfile(brandId);
  const knowledgeGaps = useKnowledgeGaps(brandId);
  const runGapAnalysis = useRunGapAnalysis(brandId);
  const generateJsonLd = useGenerateJsonLd(brandId);
  const [jsonLdOutput, setJsonLdOutput] = useState<string | null>(null);

  const completeness = entityProfile.data?.completeness_score ?? 0;

  // Dimension completeness radar data (8 dimensions)
  const dimensionNames = [
    "Identity",
    "Products",
    "Expertise",
    "Social Proof",
    "Market Position",
    "Culture",
    "Technology",
    "Partnerships",
  ];

  const dimensions = entityProfile.data?.dimensions ?? [];
  const radarData = dimensionNames.map((name) => {
    const dim = dimensions.find(
      (d) => d.name.toLowerCase() === name.toLowerCase()
    );
    return {
      dimension: name,
      completeness: dim ? dim.confidence * 100 : 0,
      fullMark: 100,
    };
  });

  const gaps = knowledgeGaps.data?.gaps ?? [];

  const handleRunGapAnalysis = async () => {
    try {
      await runGapAnalysis.mutateAsync({
        target_engines: ["claude", "gpt-4o", "gemini", "perplexity"],
        depth: "standard",
      });
    } catch {
      // handled
    }
  };

  const handleGenerateJsonLd = async () => {
    try {
      const result = await generateJsonLd.mutateAsync();
      setJsonLdOutput(JSON.stringify(result.json_ld, null, 2));
    } catch {
      // handled
    }
  };

  const severityVariant = (severity: number) => {
    if (severity >= 0.7) return "danger" as const;
    if (severity >= 0.4) return "warning" as const;
    return "info" as const;
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="GRAPH"
        subtitle="Knowledge graph entity profile management"
        actions={
          <div className="flex gap-3">
            <button
              onClick={handleRunGapAnalysis}
              disabled={runGapAnalysis.isPending}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <SearchIcon size={14} />
              {runGapAnalysis.isPending ? "Analyzing..." : "Run Gap Analysis"}
            </button>
            <button
              onClick={handleGenerateJsonLd}
              disabled={generateJsonLd.isPending}
              className="btn-primary flex items-center gap-2 text-sm"
            >
              <Code size={14} />
              {generateJsonLd.isPending ? "Generating..." : "Generate JSON-LD"}
            </button>
          </div>
        }
      />

      {/* Entity Health + Radar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Entity Health Gauge */}
        <div className="glass-panel p-6 flex flex-col items-center justify-center">
          <ScoreGauge
            score={completeness * 100}
            size={160}
            label="Entity Health"
            sublabel="Completeness"
          />
          <div className="mt-4 text-center">
            <p className="text-sm text-gray-400">
              {entityProfile.data?.entity_name || brandId}
            </p>
            <p className="text-xs text-gray-600 mt-0.5">
              {entityProfile.data?.entity_type || "Organization"}
            </p>
          </div>
          <button
            onClick={() => navigate(`/graph/profile`)}
            className="mt-4 btn-ghost text-xs"
          >
            Edit Entity Profile
          </button>
        </div>

        {/* Dimension Completeness Radar */}
        <div className="lg:col-span-2 glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Dimension Completeness
          </h2>
          <ResponsiveContainer width="100%" height={320}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="rgba(255,255,255,0.06)" />
              <PolarAngleAxis
                dataKey="dimension"
                tick={{ fill: "#9ca3af", fontSize: 11 }}
              />
              <PolarRadiusAxis
                angle={90}
                domain={[0, 100]}
                tick={{ fill: "#6b7280", fontSize: 10 }}
                axisLine={false}
              />
              <Radar
                name="Completeness"
                dataKey="completeness"
                stroke="#00d4ff"
                fill="#00d4ff"
                fillOpacity={0.15}
                strokeWidth={2}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="bg-card border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl text-sm">
                      <p className="text-gray-200">{payload[0].payload.dimension}</p>
                      <p className="text-accent">{payload[0].value}%</p>
                    </div>
                  );
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Knowledge Gaps + JSON-LD Output */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Knowledge Gaps */}
        <div className="glass-panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-200">
              Knowledge Gaps
            </h2>
            {gaps.length > 0 && (
              <Badge variant="warning">{gaps.length} gaps</Badge>
            )}
          </div>

          {gaps.length > 0 ? (
            <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
              {gaps
                .sort((a, b) => b.severity - a.severity)
                .map((gap) => (
                  <div
                    key={gap.gap_id}
                    className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <AlertCircle
                        size={14}
                        className={
                          gap.severity >= 0.7
                            ? "text-danger"
                            : gap.severity >= 0.4
                            ? "text-warning"
                            : "text-accent"
                        }
                      />
                      <span className="text-sm font-medium text-gray-200">
                        {gap.dimension}
                      </span>
                      <Badge variant={severityVariant(gap.severity)}>
                        {(gap.severity * 100).toFixed(0)}% severity
                      </Badge>
                    </div>
                    <p className="text-xs text-gray-400 mb-1.5">
                      {gap.description}
                    </p>
                    <div className="flex items-center gap-2">
                      <Badge variant="neutral">{gap.engine}</Badge>
                      <span className="text-xs text-gray-500">
                        {gap.suggested_action}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <EmptyState
              title="No knowledge gaps detected"
              description="Run a gap analysis to discover missing or inconsistent information"
              action={{
                label: "Run Gap Analysis",
                onClick: handleRunGapAnalysis,
              }}
            />
          )}
        </div>

        {/* JSON-LD Output */}
        <div className="glass-panel p-6">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            JSON-LD Preview
          </h2>
          {jsonLdOutput ? (
            <div className="relative">
              <pre className="p-4 rounded-lg bg-surface/80 border border-white/[0.04] text-xs font-mono text-gray-300 overflow-x-auto max-h-[400px] overflow-y-auto">
                {jsonLdOutput}
              </pre>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(jsonLdOutput);
                }}
                className="absolute top-2 right-2 btn-ghost text-xs px-2 py-1"
              >
                Copy
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[200px] text-gray-600 text-sm">
              Click "Generate JSON-LD" to preview structured data
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
