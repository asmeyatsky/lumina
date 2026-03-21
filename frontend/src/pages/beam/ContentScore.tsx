import { useState } from "react";
import { Link as LinkIcon, RefreshCw, Sparkles } from "lucide-react";
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
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { useScoreContent } from "@/hooks/useApi";
import { beam } from "@/api/client";
import type { ContentScoreResponse, RewriteSuggestion, RAGSimulationResponse } from "@/types";

interface ContentScorePageProps {
  brandId: string;
}

const FACTOR_LABELS: Record<string, string> = {
  entity_density: "Entity Density",
  answer_shape: "Answer Shape",
  fact_citability: "Fact Citability",
  rag_survivability: "RAG Survivability",
  semantic_authority: "Semantic Authority",
  freshness: "Freshness",
  ai_readability: "AI Readability",
  chunking_quality: "Chunking Quality",
  factual_density: "Factual Density",
  structural_clarity: "Structural Clarity",
};

export default function ContentScorePage({ brandId }: ContentScorePageProps) {
  const [url, setUrl] = useState("");
  const scoreContent = useScoreContent();
  const [scoreResult, setScoreResult] = useState<ContentScoreResponse | null>(null);
  const [rewrites, setRewrites] = useState<RewriteSuggestion[]>([]);
  const [ragResult, setRagResult] = useState<RAGSimulationResponse | null>(null);
  const [loadingRewrites, setLoadingRewrites] = useState(false);
  const [loadingRag, setLoadingRag] = useState(false);
  const [ragQuery, setRagQuery] = useState("");

  const handleScore = async () => {
    if (!url.trim()) return;
    try {
      const result = await scoreContent.mutateAsync({
        url: url.trim(),
        brand_id: brandId,
      });
      setScoreResult(result);
      setRewrites([]);
      setRagResult(null);
    } catch {
      // handled
    }
  };

  const handleGetRewrites = async () => {
    if (!scoreResult) return;
    setLoadingRewrites(true);
    try {
      const result = await beam.getRewrites(scoreResult.asset_id, {
        target_score: 80,
      });
      setRewrites(result.suggestions);
    } catch {
      // handled
    } finally {
      setLoadingRewrites(false);
    }
  };

  const handleRagSimulation = async () => {
    if (!scoreResult || !ragQuery.trim()) return;
    setLoadingRag(true);
    try {
      const result = await beam.runRagSimulation(scoreResult.asset_id, {
        query: ragQuery.trim(),
      });
      setRagResult(result);
    } catch {
      // handled
    } finally {
      setLoadingRag(false);
    }
  };

  // Build radar data from dimensions
  const radarData = scoreResult
    ? Object.entries(scoreResult.dimensions).map(([key, value]) => ({
        factor: FACTOR_LABELS[key] || key,
        score: value * 100,
        fullMark: 100,
      }))
    : [];

  // Build factor breakdown for bar display
  const factorBreakdown = scoreResult
    ? Object.entries(scoreResult.dimensions).map(([key, value]) => ({
        key,
        label: FACTOR_LABELS[key] || key,
        score: value * 100,
      }))
    : [];

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Content Scoring"
        subtitle="Score content assets for AI engine optimization"
      />

      {/* URL Input */}
      <div className="glass-panel p-6 mb-6">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <LinkIcon
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
            />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleScore()}
              placeholder="Enter URL to score (e.g., https://example.com/page)"
              className="input-field pl-9"
            />
          </div>
          <button
            onClick={handleScore}
            disabled={scoreContent.isPending || !url.trim()}
            className="btn-primary flex items-center gap-2 disabled:opacity-40"
          >
            {scoreContent.isPending ? (
              <LoadingSpinner size={16} />
            ) : (
              <Sparkles size={16} />
            )}
            Score
          </button>
        </div>
      </div>

      {/* Results */}
      {scoreResult && (
        <div className="space-y-6 animate-slide-up">
          {/* Score Overview + Radar */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Overall Score */}
            <div className="glass-panel p-6 flex flex-col items-center">
              <ScoreGauge
                score={scoreResult.overall_score * 100}
                size={160}
                label="Overall GEO Score"
              />
              <div className="mt-4 text-center">
                <p className="text-xs text-gray-500 font-mono truncate max-w-[200px]">
                  {scoreResult.url}
                </p>
              </div>
            </div>

            {/* Radar Chart */}
            <div className="lg:col-span-2 glass-panel p-6">
              <h2 className="text-base font-semibold text-gray-200 mb-4">
                Factor Analysis
              </h2>
              {radarData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="rgba(255,255,255,0.06)" />
                    <PolarAngleAxis
                      dataKey="factor"
                      tick={{ fill: "#9ca3af", fontSize: 10 }}
                    />
                    <PolarRadiusAxis
                      angle={90}
                      domain={[0, 100]}
                      tick={{ fill: "#6b7280", fontSize: 10 }}
                      axisLine={false}
                    />
                    <Radar
                      name="Score"
                      dataKey="score"
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
                            <p className="text-gray-200">{payload[0].payload.factor}</p>
                            <p className="text-accent">{Number(payload[0].value).toFixed(1)}%</p>
                          </div>
                        );
                      }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[300px] text-gray-600 text-sm">
                  No factor data available
                </div>
              )}
            </div>
          </div>

          {/* Factor Breakdown Bars */}
          <div className="glass-panel p-6">
            <h2 className="text-base font-semibold text-gray-200 mb-4">
              Factor-by-Factor Breakdown
            </h2>
            <div className="space-y-4">
              {factorBreakdown.map((f) => (
                <div key={f.key}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-gray-300">{f.label}</span>
                    <span
                      className={`text-sm font-medium ${
                        f.score >= 70
                          ? "text-success"
                          : f.score >= 40
                          ? "text-warning"
                          : "text-danger"
                      }`}
                    >
                      {f.score.toFixed(0)}
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-white/[0.06] overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        f.score >= 70
                          ? "bg-success"
                          : f.score >= 40
                          ? "bg-warning"
                          : "bg-danger"
                      }`}
                      style={{ width: `${Math.min(100, f.score)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Rewrite Suggestions + RAG Simulation */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Rewrites */}
            <div className="glass-panel p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-200">
                  Rewrite Suggestions
                </h2>
                <button
                  onClick={handleGetRewrites}
                  disabled={loadingRewrites}
                  className="btn-secondary text-xs flex items-center gap-1"
                >
                  <RefreshCw size={12} className={loadingRewrites ? "animate-spin" : ""} />
                  {loadingRewrites ? "Generating..." : "Get Rewrites"}
                </button>
              </div>

              {rewrites.length > 0 ? (
                <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2">
                  {rewrites.map((rw, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="neutral">{rw.section}</Badge>
                        <Badge variant="success">
                          +{rw.expected_score_impact.toFixed(1)} pts
                        </Badge>
                      </div>
                      <div className="space-y-2">
                        <div>
                          <span className="text-[10px] uppercase tracking-wider text-gray-600">
                            Before
                          </span>
                          <p className="text-xs text-gray-500 line-through">
                            {rw.original_text}
                          </p>
                        </div>
                        <div>
                          <span className="text-[10px] uppercase tracking-wider text-success">
                            After
                          </span>
                          <p className="text-xs text-gray-300">{rw.suggested_text}</p>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 mt-2 italic">
                        {rw.improvement_reason}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-600 text-sm">
                  Click "Get Rewrites" to generate AI optimization suggestions
                </div>
              )}
            </div>

            {/* RAG Simulation */}
            <div className="glass-panel p-6">
              <h2 className="text-base font-semibold text-gray-200 mb-4">
                RAG Simulation
              </h2>
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={ragQuery}
                  onChange={(e) => setRagQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleRagSimulation()}
                  placeholder="Enter a test query"
                  className="input-field"
                />
                <button
                  onClick={handleRagSimulation}
                  disabled={loadingRag || !ragQuery.trim()}
                  className="btn-secondary text-sm flex-shrink-0 disabled:opacity-40"
                >
                  {loadingRag ? "Running..." : "Simulate"}
                </button>
              </div>

              {ragResult ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-4 p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <ScoreGauge
                      score={ragResult.retrieval_probability * 100}
                      size={80}
                      strokeWidth={6}
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-200">
                        Retrieval Probability
                      </p>
                      <p className="text-xs text-gray-500">
                        {ragResult.retrieval_probability >= 0.7
                          ? "High chance of being retrieved"
                          : ragResult.retrieval_probability >= 0.4
                          ? "Moderate retrieval chance"
                          : "Low retrieval probability"}
                      </p>
                    </div>
                  </div>

                  {ragResult.chunk_rankings.length > 0 && (
                    <div>
                      <h3 className="text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                        Chunk Rankings
                      </h3>
                      <div className="space-y-2">
                        {ragResult.chunk_rankings.map((chunk, i) => (
                          <div
                            key={i}
                            className="flex items-center gap-2 p-2 rounded bg-white/[0.02] border border-white/[0.04] text-xs"
                          >
                            <span className="text-accent font-mono">#{i + 1}</span>
                            <span className="text-gray-400 truncate">
                              {JSON.stringify(chunk).slice(0, 80)}...
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-600 text-sm">
                  Enter a query above to simulate RAG retrieval
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
