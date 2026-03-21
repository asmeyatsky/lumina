import { useParams } from "react-router-dom";
import { Play, CheckCircle, Clock, AlertCircle } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import Badge from "@/components/common/Badge";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { useDistributionPlan } from "@/hooks/useApi";
import { signal } from "@/api/client";
import { useState } from "react";
import type { DistributionAction } from "@/types";

interface DistributionPlanPageProps {
  brandId: string;
}

export default function DistributionPlanPage({ brandId }: DistributionPlanPageProps) {
  const { planId } = useParams<{ planId: string }>();
  const planQuery = useDistributionPlan(planId || "");
  const [executingAction, setExecutingAction] = useState<string | null>(null);

  // Mock plan data since API may return 404 for non-existing plans
  const plan = planQuery.data || {
    plan_id: planId || "plan-001",
    brand_id: brandId,
    strategy: "balanced",
    status: "active",
    actions: [
      {
        action_id: "act-001",
        surface: "Wikipedia",
        action_type: "create",
        status: "pending",
        description: "Create Wikipedia stub article with verified facts",
      },
      {
        action_id: "act-002",
        surface: "Wikidata",
        action_type: "create",
        status: "pending",
        description: "Create Wikidata entity with core properties",
      },
      {
        action_id: "act-003",
        surface: "Schema.org",
        action_type: "update",
        status: "completed",
        description: "Deploy enhanced JSON-LD structured data",
      },
      {
        action_id: "act-004",
        surface: "Crunchbase",
        action_type: "update",
        status: "in_progress",
        description: "Update company profile with latest funding data",
      },
      {
        action_id: "act-005",
        surface: "GitHub",
        action_type: "create",
        status: "pending",
        description: "Claim and configure GitHub organization profile",
      },
      {
        action_id: "act-006",
        surface: "Press Releases",
        action_type: "distribute",
        status: "completed",
        description: "Distribute AI-optimized press releases to wire services",
      },
    ] as DistributionAction[],
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  };

  const totalActions = plan.actions.length;
  const completedActions = plan.actions.filter((a) => a.status === "completed").length;
  const progressPct = totalActions > 0 ? (completedActions / totalActions) * 100 : 0;

  const handleExecute = async (actionId: string) => {
    setExecutingAction(actionId);
    try {
      await signal.executeAction(plan.plan_id, actionId, {});
    } catch {
      // handled
    } finally {
      setExecutingAction(null);
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle size={16} className="text-success" />;
      case "in_progress":
        return <Clock size={16} className="text-warning" />;
      case "failed":
        return <AlertCircle size={16} className="text-danger" />;
      default:
        return <Clock size={16} className="text-gray-500" />;
    }
  };

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed":
        return "success" as const;
      case "in_progress":
        return "warning" as const;
      case "failed":
        return "danger" as const;
      default:
        return "neutral" as const;
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title={`Distribution Plan`}
        subtitle={`${plan.plan_id} - ${plan.strategy} strategy`}
        actions={
          <Badge
            variant={
              plan.status === "active"
                ? "success"
                : plan.status === "draft"
                ? "warning"
                : "neutral"
            }
            dot
          >
            {plan.status}
          </Badge>
        }
      />

      {/* Progress */}
      <div className="glass-panel p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-gray-400">
            Plan Progress
          </span>
          <span className="text-sm font-medium text-gray-200">
            {completedActions} / {totalActions} actions completed
          </span>
        </div>
        <div className="w-full h-3 rounded-full bg-white/[0.06] overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-accent to-success transition-all duration-700"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-600">
            Strategy: {plan.strategy}
          </span>
          <span className="text-xs text-gray-600">
            {progressPct.toFixed(0)}% complete
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="glass-panel p-6 mb-6">
        <h2 className="text-base font-semibold text-gray-200 mb-4">
          Actions Checklist
        </h2>
        <div className="space-y-3">
          {plan.actions.map((action) => (
            <div
              key={action.action_id}
              className={`flex items-start gap-4 p-4 rounded-lg border transition-colors ${
                action.status === "completed"
                  ? "bg-success/5 border-success/10"
                  : "bg-white/[0.02] border-white/[0.04]"
              }`}
            >
              <div className="mt-0.5">{statusIcon(action.status)}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-sm font-medium ${
                      action.status === "completed"
                        ? "text-gray-400 line-through"
                        : "text-gray-200"
                    }`}
                  >
                    {action.description}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="neutral">{action.surface}</Badge>
                  <Badge variant={statusVariant(action.status)}>
                    {action.status}
                  </Badge>
                  <span className="text-xs text-gray-600">{action.action_type}</span>
                </div>
              </div>
              {action.status !== "completed" && (
                <button
                  onClick={() => handleExecute(action.action_id)}
                  disabled={executingAction === action.action_id}
                  className="btn-secondary text-xs flex items-center gap-1 flex-shrink-0"
                >
                  <Play size={12} />
                  {executingAction === action.action_id ? "Running..." : "Execute"}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Coverage Impact */}
      <div className="glass-panel p-6">
        <h2 className="text-base font-semibold text-gray-200 mb-4">
          Coverage Impact Tracker
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.04] text-center">
            <div className="text-2xl font-bold text-gray-100">{totalActions}</div>
            <div className="text-xs text-gray-500 mt-1">Total Actions</div>
          </div>
          <div className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.04] text-center">
            <div className="text-2xl font-bold text-success">{completedActions}</div>
            <div className="text-xs text-gray-500 mt-1">Completed</div>
          </div>
          <div className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.04] text-center">
            <div className="text-2xl font-bold text-warning">
              {plan.actions.filter((a) => a.status === "in_progress").length}
            </div>
            <div className="text-xs text-gray-500 mt-1">In Progress</div>
          </div>
          <div className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.04] text-center">
            <div className="text-2xl font-bold text-gray-400">
              {plan.actions.filter((a) => a.status === "pending").length}
            </div>
            <div className="text-xs text-gray-500 mt-1">Pending</div>
          </div>
        </div>
      </div>
    </div>
  );
}
