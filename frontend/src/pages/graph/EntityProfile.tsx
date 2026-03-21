import { useState } from "react";
import { Save, Plus, ChevronRight } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import Badge from "@/components/common/Badge";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { useEntityProfile } from "@/hooks/useApi";
import { graph } from "@/api/client";

interface EntityProfilePageProps {
  brandId: string;
}

const DIMENSION_TABS = [
  { key: "identity", label: "Identity" },
  { key: "products", label: "Products" },
  { key: "expertise", label: "Expertise" },
  { key: "social_proof", label: "Social Proof" },
  { key: "market_position", label: "Market Position" },
  { key: "culture", label: "Culture" },
  { key: "technology", label: "Technology" },
  { key: "partnerships", label: "Partnerships" },
];

interface DimensionFormData {
  name: string;
  value: string;
  source: string;
  confidence: number;
}

export default function EntityProfilePage({ brandId }: EntityProfilePageProps) {
  const entityProfile = useEntityProfile(brandId);
  const [activeTab, setActiveTab] = useState("identity");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<DimensionFormData>({
    name: "",
    value: "",
    source: "",
    confidence: 1.0,
  });
  const [showAddForm, setShowAddForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [jsonLdPreview, setJsonLdPreview] = useState<string | null>(null);

  const dimensions = entityProfile.data?.dimensions ?? [];
  const tabDimensions = dimensions.filter(
    (d) => d.name.toLowerCase().replace(/\s+/g, "_") === activeTab ||
    d.name.toLowerCase().startsWith(activeTab.replace("_", " "))
  );

  const completenessForTab = (tabKey: string) => {
    const tabDims = dimensions.filter(
      (d) =>
        d.name.toLowerCase().replace(/\s+/g, "_") === tabKey ||
        d.name.toLowerCase().startsWith(tabKey.replace("_", " "))
    );
    if (tabDims.length === 0) return 0;
    return tabDims.reduce((sum, d) => sum + d.confidence, 0) / tabDims.length;
  };

  const handleSave = async (dimensionId: string) => {
    setSaving(true);
    try {
      await graph.updateDimension(brandId, dimensionId, {
        value: formData.value,
        source: formData.source,
        confidence: formData.confidence,
      });
      setEditingId(null);
    } catch {
      // handled
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateJsonLd = async () => {
    try {
      const result = await graph.generateJsonLd(brandId, {
        schema_type: "Organization",
      });
      setJsonLdPreview(JSON.stringify(result.json_ld, null, 2));
    } catch {
      // handled
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Entity Profile"
        subtitle={entityProfile.data?.entity_name || brandId}
        actions={
          <button
            onClick={handleGenerateJsonLd}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            Preview JSON-LD
          </button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Dimension Tabs */}
        <div className="glass-panel p-3">
          <nav className="space-y-0.5">
            {DIMENSION_TABS.map((tab) => {
              const comp = completenessForTab(tab.key);
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    activeTab === tab.key
                      ? "bg-accent/10 text-accent"
                      : "text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]"
                  }`}
                >
                  <span>{tab.label}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-accent transition-all"
                        style={{ width: `${comp * 100}%` }}
                      />
                    </div>
                    <ChevronRight
                      size={14}
                      className={activeTab === tab.key ? "text-accent" : "text-gray-600"}
                    />
                  </div>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Dimension Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Dimension List */}
          <div className="glass-panel p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-gray-200 capitalize">
                {activeTab.replace("_", " ")} Dimensions
              </h2>
              <button
                onClick={() => setShowAddForm(!showAddForm)}
                className="btn-ghost text-xs flex items-center gap-1"
              >
                <Plus size={14} /> Add Dimension
              </button>
            </div>

            {showAddForm && (
              <div className="p-4 mb-4 rounded-lg bg-white/[0.02] border border-white/[0.06] animate-slide-up">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="label">Name</label>
                    <input
                      type="text"
                      placeholder="Dimension name"
                      className="input-field"
                      value={formData.name}
                      onChange={(e) =>
                        setFormData({ ...formData, name: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <label className="label">Source</label>
                    <input
                      type="text"
                      placeholder="Data source URL or reference"
                      className="input-field"
                      value={formData.source}
                      onChange={(e) =>
                        setFormData({ ...formData, source: e.target.value })
                      }
                    />
                  </div>
                </div>
                <div className="mb-3">
                  <label className="label">Value</label>
                  <textarea
                    placeholder="Dimension value/content"
                    className="input-field min-h-[80px] resize-y"
                    value={formData.value}
                    onChange={(e) =>
                      setFormData({ ...formData, value: e.target.value })
                    }
                  />
                </div>
                <div className="mb-3">
                  <label className="label">
                    Confidence: {(formData.confidence * 100).toFixed(0)}%
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={formData.confidence}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        confidence: parseFloat(e.target.value),
                      })
                    }
                    className="w-full accent-accent"
                  />
                </div>
                <div className="flex gap-2">
                  <button className="btn-primary text-xs">Save</button>
                  <button
                    onClick={() => setShowAddForm(false)}
                    className="btn-ghost text-xs"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {tabDimensions.length > 0 ? (
              <div className="space-y-3">
                {tabDimensions.map((dim) => (
                  <div
                    key={dim.dimension_id}
                    className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                  >
                    {editingId === dim.dimension_id ? (
                      <div className="space-y-3">
                        <div>
                          <label className="label">Value</label>
                          <textarea
                            value={formData.value}
                            onChange={(e) =>
                              setFormData({ ...formData, value: e.target.value })
                            }
                            className="input-field min-h-[80px] resize-y"
                          />
                        </div>
                        <div>
                          <label className="label">Source</label>
                          <input
                            type="text"
                            value={formData.source}
                            onChange={(e) =>
                              setFormData({ ...formData, source: e.target.value })
                            }
                            className="input-field"
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSave(dim.dimension_id)}
                            disabled={saving}
                            className="btn-primary text-xs flex items-center gap-1"
                          >
                            <Save size={12} />
                            {saving ? "Saving..." : "Save"}
                          </button>
                          <button
                            onClick={() => setEditingId(null)}
                            className="btn-ghost text-xs"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-200">
                            {dim.name}
                          </span>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={
                                dim.confidence >= 0.8
                                  ? "success"
                                  : dim.confidence >= 0.5
                                  ? "warning"
                                  : "danger"
                              }
                            >
                              {(dim.confidence * 100).toFixed(0)}%
                            </Badge>
                            <button
                              onClick={() => {
                                setEditingId(dim.dimension_id);
                                setFormData({
                                  name: dim.name,
                                  value: dim.value,
                                  source: dim.source,
                                  confidence: dim.confidence,
                                });
                              }}
                              className="btn-ghost text-xs px-2 py-1"
                            >
                              Edit
                            </button>
                          </div>
                        </div>
                        <p className="text-sm text-gray-400 mb-1">{dim.value}</p>
                        {dim.source && (
                          <p className="text-xs text-gray-600">
                            Source: {dim.source}
                          </p>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-600 text-sm">
                No dimensions in this category yet. Add one above.
              </div>
            )}
          </div>

          {/* JSON-LD Preview */}
          {jsonLdPreview && (
            <div className="glass-panel p-6 animate-slide-up">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-200">
                  JSON-LD Preview
                </h2>
                <button
                  onClick={() => navigator.clipboard.writeText(jsonLdPreview)}
                  className="btn-ghost text-xs"
                >
                  Copy
                </button>
              </div>
              <pre className="p-4 rounded-lg bg-surface/80 border border-white/[0.04] text-xs font-mono text-gray-300 overflow-x-auto">
                {jsonLdPreview}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
