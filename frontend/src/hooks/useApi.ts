import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { pulse, graph, beam, signal, intelligence } from "@/api/client";
import type {
  TriggerMonitoringRunRequest,
  CreatePromptBatteryRequest,
  ScoreContentRequest,
  BulkAuditRequest,
  CreateDistributionPlanRequest,
  RunRootCauseRequest,
  CalculateAVSRequest,
  GeneratePRBriefRequest,
  RunGapAnalysisRequest,
} from "@/types";

// =============================================================================
// Intelligence Hooks
// =============================================================================

export function useAvs(brandId: string) {
  return useQuery({
    queryKey: ["avs", brandId],
    queryFn: () => intelligence.getAvs(brandId),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useAvsTrends(brandId: string, period = "30d") {
  return useQuery({
    queryKey: ["avs-trends", brandId, period],
    queryFn: () => intelligence.getAvsTrends(brandId, period),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useCalculateAvs(brandId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data?: CalculateAVSRequest) =>
      intelligence.calculateAvs(brandId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["avs", brandId] });
      queryClient.invalidateQueries({ queryKey: ["avs-trends", brandId] });
    },
  });
}

export function useRecommendations(brandId: string) {
  return useQuery({
    queryKey: ["recommendations", brandId],
    queryFn: () => intelligence.getRecommendations(brandId),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useRootCause(brandId: string) {
  return useMutation({
    mutationFn: (data: RunRootCauseRequest) =>
      intelligence.runRootCause(brandId, data),
  });
}

// =============================================================================
// PULSE Hooks
// =============================================================================

export function useCitationTrends(brandId: string, period = "30d") {
  return useQuery({
    queryKey: ["citation-trends", brandId, period],
    queryFn: () => pulse.getTrends(brandId, period),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useShareOfVoice(brandId: string, category = "general") {
  return useQuery({
    queryKey: ["share-of-voice", brandId, category],
    queryFn: () => pulse.getShareOfVoice(brandId, category),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useRunMonitoring() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TriggerMonitoringRunRequest) => pulse.runMonitoring(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["citation-trends"] });
      queryClient.invalidateQueries({ queryKey: ["share-of-voice"] });
    },
  });
}

export function useCreateBattery() {
  return useMutation({
    mutationFn: (data: CreatePromptBatteryRequest) => pulse.createBattery(data),
  });
}

export function useRunDetails(runId: string) {
  return useQuery({
    queryKey: ["monitoring-run", runId],
    queryFn: () => pulse.getRunDetails(runId),
    enabled: !!runId,
    retry: 1,
  });
}

// =============================================================================
// GRAPH Hooks
// =============================================================================

export function useEntityProfile(brandId: string) {
  return useQuery({
    queryKey: ["entity-profile", brandId],
    queryFn: () => graph.getProfile(brandId),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useKnowledgeGaps(brandId: string) {
  return useQuery({
    queryKey: ["knowledge-gaps", brandId],
    queryFn: () => graph.getGaps(brandId),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useRunGapAnalysis(brandId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data?: RunGapAnalysisRequest) =>
      graph.runGapAnalysis(brandId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-gaps", brandId] });
    },
  });
}

export function useGenerateJsonLd(brandId: string) {
  return useMutation({
    mutationFn: () => graph.generateJsonLd(brandId),
  });
}

// =============================================================================
// BEAM Hooks
// =============================================================================

export function useAuditSummary(brandId: string) {
  return useQuery({
    queryKey: ["audit-summary", brandId],
    queryFn: () => beam.getAuditSummary(brandId),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useContentScore(assetId: string) {
  return useQuery({
    queryKey: ["content-score", assetId],
    queryFn: () => beam.getScore(assetId),
    enabled: !!assetId,
    retry: 1,
  });
}

export function useScoreContent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ScoreContentRequest) => beam.scoreContent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    },
  });
}

export function useBulkAudit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: BulkAuditRequest) => beam.bulkAudit(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["audit-summary"] });
    },
  });
}

// =============================================================================
// SIGNAL Hooks
// =============================================================================

export function useDistributionCoverage(brandId: string) {
  return useQuery({
    queryKey: ["distribution-coverage", brandId],
    queryFn: () => signal.getCoverage(brandId),
    enabled: !!brandId,
    retry: 1,
  });
}

export function useCreatePlan() {
  return useMutation({
    mutationFn: (data: CreateDistributionPlanRequest) => signal.createPlan(data),
  });
}

export function useDistributionPlan(planId: string) {
  return useQuery({
    queryKey: ["distribution-plan", planId],
    queryFn: () => signal.getPlan(planId),
    enabled: !!planId,
    retry: 1,
  });
}

export function useGeneratePrBrief(brandId: string) {
  return useMutation({
    mutationFn: (data: GeneratePRBriefRequest) =>
      signal.generatePrBrief(brandId, data),
  });
}
