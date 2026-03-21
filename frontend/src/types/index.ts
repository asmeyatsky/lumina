// =============================================================================
// Common Types
// =============================================================================

export type AIEngine = "claude" | "gpt-4o" | "gemini" | "perplexity";

export interface ErrorResponse {
  detail: string;
  error_type: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  service: string;
}

// =============================================================================
// PULSE Types
// =============================================================================

export interface TriggerMonitoringRunRequest {
  brand_id: string;
  engines?: AIEngine[];
  prompt_battery_id?: string | null;
}

export interface MonitoringRunResponse {
  run_id: string;
  brand_id: string;
  status: string;
  engines: string[];
  created_at: string;
  completed_at: string | null;
  results_count: number;
}

export interface CreatePromptBatteryRequest {
  brand_id: string;
  name: string;
  prompts: string[];
  category?: string;
}

export interface PromptBatteryResponse {
  battery_id: string;
  brand_id: string;
  name: string;
  prompts: string[];
  category: string;
  created_at: string;
}

export interface CitationTrendPoint {
  timestamp: string;
  citation_rate: number;
  engine: string;
}

export interface CitationTrendsResponse {
  brand_id: string;
  period: string;
  data_points: CitationTrendPoint[];
  trend_direction: string;
  change_rate: number;
}

export interface ShareOfVoiceEntry {
  entity: string;
  share: number;
  citation_count: number;
}

export interface ShareOfVoiceResponse {
  brand_id: string;
  category: string;
  entries: ShareOfVoiceEntry[];
  calculated_at: string;
}

// =============================================================================
// GRAPH Types
// =============================================================================

export interface DimensionInput {
  name: string;
  value: string;
  source?: string;
  confidence?: number;
}

export interface CreateEntityProfileRequest {
  brand_id: string;
  entity_name: string;
  entity_type?: string;
  description?: string;
  dimensions?: DimensionInput[] | null;
}

export interface DimensionResponse {
  dimension_id: string;
  name: string;
  value: string;
  source: string;
  confidence: number;
  updated_at: string;
}

export interface EntityProfileResponse {
  brand_id: string;
  entity_name: string;
  entity_type: string;
  description: string;
  dimensions: DimensionResponse[];
  completeness_score: number;
  created_at: string;
  updated_at: string;
}

export interface UpdateDimensionRequest {
  value: string;
  source?: string;
  confidence?: number;
}

export interface RunGapAnalysisRequest {
  target_engines?: string[];
  depth?: string;
}

export interface KnowledgeGapResponse {
  gap_id: string;
  dimension: string;
  severity: number;
  description: string;
  suggested_action: string;
  engine: string;
}

export interface GapAnalysisResponse {
  brand_id: string;
  gaps: KnowledgeGapResponse[];
  total_gaps: number;
  analysis_completed_at: string;
}

export interface GenerateJsonLdRequest {
  schema_type?: string;
  include_dimensions?: string[] | null;
}

export interface JsonLdResponse {
  brand_id: string;
  schema_type: string;
  json_ld: Record<string, unknown>;
  generated_at: string;
}

// =============================================================================
// BEAM Types
// =============================================================================

export interface ScoreContentRequest {
  url: string;
  brand_id: string;
  content_type?: string;
}

export interface ContentScoreResponse {
  asset_id: string;
  url: string;
  brand_id: string;
  overall_score: number;
  dimensions: Record<string, number>;
  ai_readability: number;
  chunking_quality: number;
  factual_density: number;
  scored_at: string;
}

export interface BulkAuditRequest {
  brand_id: string;
  urls: string[];
  content_type?: string;
}

export interface BulkAuditResponse {
  audit_id: string;
  brand_id: string;
  total_urls: number;
  status: string;
  results: ContentScoreResponse[];
  started_at: string;
  completed_at: string | null;
}

export interface RAGSimulationRequest {
  query: string;
  target_engines?: string[];
}

export interface RAGSimulationResponse {
  asset_id: string;
  query: string;
  retrieval_probability: number;
  chunk_rankings: Record<string, unknown>[];
  simulation_completed_at: string;
}

export interface RewriteSuggestion {
  section: string;
  original_text: string;
  suggested_text: string;
  improvement_reason: string;
  expected_score_impact: number;
}

export interface RewriteSuggestionsRequest {
  target_score?: number;
  focus_areas?: string[] | null;
}

export interface RewriteSuggestionsResponse {
  asset_id: string;
  suggestions: RewriteSuggestion[];
  current_score: number;
  projected_score: number;
  generated_at: string;
}

export interface AuditSummaryResponse {
  brand_id: string;
  total_assets: number;
  average_score: number;
  score_distribution: Record<string, number>;
  top_issues: string[];
  summary_generated_at: string;
}

// =============================================================================
// SIGNAL Types
// =============================================================================

export interface CreateDistributionPlanRequest {
  brand_id: string;
  target_surfaces?: string[];
  strategy?: string;
  priority?: string;
}

export interface DistributionAction {
  action_id: string;
  surface: string;
  action_type: string;
  status: string;
  description: string;
}

export interface DistributionPlanResponse {
  plan_id: string;
  brand_id: string;
  strategy: string;
  status: string;
  actions: DistributionAction[];
  created_at: string;
  updated_at: string;
}

export interface ExecuteActionRequest {
  parameters?: Record<string, string>;
}

export interface ExecuteActionResponse {
  action_id: string;
  plan_id: string;
  status: string;
  result: Record<string, unknown>;
  executed_at: string;
}

export interface CoverageSurface {
  surface: string;
  coverage_percentage: number;
  last_submission: string | null;
  status: string;
}

export interface DistributionCoverageResponse {
  brand_id: string;
  overall_coverage: number;
  surfaces: CoverageSurface[];
  calculated_at: string;
}

export interface GeneratePRBriefRequest {
  topic: string;
  target_publications?: string[];
  tone?: string;
}

export interface PRBriefResponse {
  brief_id: string;
  brand_id: string;
  topic: string;
  headline: string;
  body: string;
  target_publications: string[];
  generated_at: string;
}

export interface MapSurfacesRequest {
  categories?: string[];
  include_competitors?: boolean;
}

export interface SurfaceMapping {
  surface_id: string;
  name: string;
  url: string;
  category: string;
  crawl_frequency: string;
  relevance_score: number;
}

export interface MapSurfacesResponse {
  brand_id: string;
  surfaces: SurfaceMapping[];
  total_surfaces: number;
  mapped_at: string;
}

// =============================================================================
// Intelligence Engine Types
// =============================================================================

export interface CalculateAVSRequest {
  weights?: Record<string, number> | null;
}

export interface ScoreComponentResponse {
  module_name: string;
  score: number;
  weight: number;
  weighted_score: number;
}

export interface AVSResponse {
  id: string;
  brand_id: string;
  overall_score: number;
  components: ScoreComponentResponse[];
  delta: number;
  previous_score: number | null;
  calculated_at: string;
}

export interface AVSTrendPoint {
  timestamp: string;
  score: number;
}

export interface AVSTrendsResponse {
  brand_id: string;
  period: string;
  trend_direction: string;
  change_rate: number;
  data_points: AVSTrendPoint[];
}

export interface RecommendationResponse {
  id: string;
  source_module: string;
  action_description: string;
  expected_avs_impact: number;
  effort_level: string;
  priority_rank: number;
  linked_entity_id: string;
  created_at: string;
}

export interface RecommendationQueueResponse {
  brand_id: string;
  recommendations: RecommendationResponse[];
  total_count: number;
}

export interface RunRootCauseRequest {
  current_scores: Record<string, number>;
  previous_scores: Record<string, number>;
  external_signals?: string[];
}

export interface RootCauseResponse {
  factor: string;
  module: string;
  evidence: string;
  contribution_weight: number;
}

export interface RootCauseAnalysisResponse {
  id: string;
  brand_id: string;
  trigger: string;
  causes: RootCauseResponse[];
  recommended_actions: string[];
  analyzed_at: string;
}

// =============================================================================
// UI-specific Types
// =============================================================================

export interface BrandConfig {
  id: string;
  name: string;
  verticals: string[];
  competitors: string[];
}

export interface AlertItem {
  id: string;
  type: "warning" | "danger" | "info" | "success";
  title: string;
  message: string;
  timestamp: string;
  module: string;
  read: boolean;
}

export interface StatCardData {
  label: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: string;
}
