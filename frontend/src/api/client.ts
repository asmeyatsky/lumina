import type {
  TriggerMonitoringRunRequest,
  MonitoringRunResponse,
  CreatePromptBatteryRequest,
  PromptBatteryResponse,
  CitationTrendsResponse,
  ShareOfVoiceResponse,
  CreateEntityProfileRequest,
  EntityProfileResponse,
  UpdateDimensionRequest,
  DimensionResponse,
  RunGapAnalysisRequest,
  GapAnalysisResponse,
  GenerateJsonLdRequest,
  JsonLdResponse,
  ScoreContentRequest,
  ContentScoreResponse,
  BulkAuditRequest,
  BulkAuditResponse,
  RAGSimulationRequest,
  RAGSimulationResponse,
  RewriteSuggestionsRequest,
  RewriteSuggestionsResponse,
  AuditSummaryResponse,
  CreateDistributionPlanRequest,
  DistributionPlanResponse,
  ExecuteActionRequest,
  ExecuteActionResponse,
  DistributionCoverageResponse,
  GeneratePRBriefRequest,
  PRBriefResponse,
  MapSurfacesRequest,
  MapSurfacesResponse,
  CalculateAVSRequest,
  AVSResponse,
  AVSTrendsResponse,
  RecommendationQueueResponse,
  RunRootCauseRequest,
  RootCauseAnalysisResponse,
} from "@/types";

const BASE_URL = "/api/v1";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public errorType: string
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const tenantId = localStorage.getItem("lumina_tenant_id");
  if (tenantId) {
    headers["X-Tenant-ID"] = tenantId;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = "An unexpected error occurred";
    let errorType = "error";
    try {
      const body = await response.json();
      detail = body.detail || detail;
      errorType = body.error_type || errorType;
    } catch {
      // Response is not JSON
    }
    throw new ApiError(response.status, detail, errorType);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    body: body ? JSON.stringify(body) : undefined,
  });
}

// =============================================================================
// PULSE API
// =============================================================================

export const pulse = {
  runMonitoring(data: TriggerMonitoringRunRequest): Promise<MonitoringRunResponse> {
    return post("/pulse/monitoring-runs", data);
  },

  getRunDetails(runId: string): Promise<MonitoringRunResponse> {
    return get(`/pulse/monitoring-runs/${runId}`);
  },

  createBattery(data: CreatePromptBatteryRequest): Promise<PromptBatteryResponse> {
    return post("/pulse/batteries", data);
  },

  getTrends(brandId: string, period = "30d"): Promise<CitationTrendsResponse> {
    return get(`/pulse/brands/${brandId}/trends?period=${period}`);
  },

  getShareOfVoice(brandId: string, category = "general"): Promise<ShareOfVoiceResponse> {
    return get(`/pulse/brands/${brandId}/share-of-voice?category=${category}`);
  },
};

// =============================================================================
// GRAPH API
// =============================================================================

export const graph = {
  createProfile(data: CreateEntityProfileRequest): Promise<EntityProfileResponse> {
    return post("/graph/profiles", data);
  },

  getProfile(brandId: string): Promise<EntityProfileResponse> {
    return get(`/graph/profiles/${brandId}`);
  },

  updateDimension(
    brandId: string,
    dimensionId: string,
    data: UpdateDimensionRequest
  ): Promise<DimensionResponse> {
    return put(`/graph/profiles/${brandId}/dimensions/${dimensionId}`, data);
  },

  runGapAnalysis(brandId: string, data?: RunGapAnalysisRequest): Promise<GapAnalysisResponse> {
    return post(`/graph/profiles/${brandId}/gap-analysis`, data || {});
  },

  getGaps(brandId: string): Promise<GapAnalysisResponse> {
    return get(`/graph/profiles/${brandId}/gaps`);
  },

  generateJsonLd(brandId: string, data?: GenerateJsonLdRequest): Promise<JsonLdResponse> {
    return post(`/graph/profiles/${brandId}/json-ld`, data || {});
  },
};

// =============================================================================
// BEAM API
// =============================================================================

export const beam = {
  scoreContent(data: ScoreContentRequest): Promise<ContentScoreResponse> {
    return post("/beam/score", data);
  },

  bulkAudit(data: BulkAuditRequest): Promise<BulkAuditResponse> {
    return post("/beam/bulk-audit", data);
  },

  getScore(assetId: string): Promise<ContentScoreResponse> {
    return get(`/beam/assets/${assetId}/score`);
  },

  runRagSimulation(assetId: string, data: RAGSimulationRequest): Promise<RAGSimulationResponse> {
    return post(`/beam/assets/${assetId}/rag-simulation`, data);
  },

  getRewrites(assetId: string, data?: RewriteSuggestionsRequest): Promise<RewriteSuggestionsResponse> {
    return post(`/beam/assets/${assetId}/rewrites`, data || {});
  },

  getAuditSummary(brandId: string): Promise<AuditSummaryResponse> {
    return get(`/beam/brands/${brandId}/audit-summary`);
  },
};

// =============================================================================
// SIGNAL API
// =============================================================================

export const signal = {
  createPlan(data: CreateDistributionPlanRequest): Promise<DistributionPlanResponse> {
    return post("/signal/plans", data);
  },

  getPlan(planId: string): Promise<DistributionPlanResponse> {
    return get(`/signal/plans/${planId}`);
  },

  executeAction(
    planId: string,
    actionId: string,
    data?: ExecuteActionRequest
  ): Promise<ExecuteActionResponse> {
    return post(`/signal/plans/${planId}/actions/${actionId}/execute`, data || {});
  },

  getCoverage(brandId: string): Promise<DistributionCoverageResponse> {
    return get(`/signal/brands/${brandId}/coverage`);
  },

  generatePrBrief(brandId: string, data: GeneratePRBriefRequest): Promise<PRBriefResponse> {
    return post(`/signal/brands/${brandId}/pr-briefs`, data);
  },

  mapSurfaces(brandId: string, data?: MapSurfacesRequest): Promise<MapSurfacesResponse> {
    return post(`/signal/brands/${brandId}/map-surfaces`, data || {});
  },
};

// =============================================================================
// Intelligence API
// =============================================================================

export const intelligence = {
  calculateAvs(brandId: string, data?: CalculateAVSRequest): Promise<AVSResponse> {
    return post(`/intelligence/brands/${brandId}/avs`, data || {});
  },

  getAvs(brandId: string): Promise<AVSResponse> {
    return get(`/intelligence/brands/${brandId}/avs`);
  },

  getAvsTrends(brandId: string, period = "30d"): Promise<AVSTrendsResponse> {
    return get(`/intelligence/brands/${brandId}/avs/trends?period=${period}`);
  },

  getRecommendations(brandId: string): Promise<RecommendationQueueResponse> {
    return get(`/intelligence/brands/${brandId}/recommendations`);
  },

  runRootCause(brandId: string, data: RunRootCauseRequest): Promise<RootCauseAnalysisResponse> {
    return post(`/intelligence/brands/${brandId}/root-cause`, data);
  },
};
