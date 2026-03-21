import { useState } from "react";
import { Plus, X, Battery, ChevronRight } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import Badge from "@/components/common/Badge";
import EmptyState from "@/components/common/EmptyState";
import { useCreateBattery } from "@/hooks/useApi";

interface PromptBatteriesProps {
  brandId: string;
}

interface BatteryItem {
  battery_id: string;
  name: string;
  category: string;
  prompts: string[];
  created_at: string;
}

export default function PromptBatteries({ brandId }: PromptBatteriesProps) {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("general");
  const [promptInput, setPromptInput] = useState("");
  const [prompts, setPrompts] = useState<string[]>([]);
  const [selectedBattery, setSelectedBattery] = useState<BatteryItem | null>(null);
  const createBattery = useCreateBattery();

  // Mock batteries
  const [batteries, setBatteries] = useState<BatteryItem[]>([
    {
      battery_id: "bat-001",
      name: "Product Discovery",
      category: "product",
      prompts: [
        "What is the best tool for X?",
        "Compare top solutions in category Y",
        "Which companies provide Z services?",
      ],
      created_at: new Date(Date.now() - 604800000).toISOString(),
    },
    {
      battery_id: "bat-002",
      name: "Brand Awareness",
      category: "brand",
      prompts: [
        "Tell me about {brand_name}",
        "What does {brand_name} do?",
        "Is {brand_name} a good choice for X?",
      ],
      created_at: new Date(Date.now() - 1209600000).toISOString(),
    },
  ]);

  const addPrompt = () => {
    if (promptInput.trim()) {
      setPrompts([...prompts, promptInput.trim()]);
      setPromptInput("");
    }
  };

  const removePrompt = (index: number) => {
    setPrompts(prompts.filter((_, i) => i !== index));
  };

  const handleCreate = async () => {
    if (!name.trim() || prompts.length === 0) return;
    try {
      const result = await createBattery.mutateAsync({
        brand_id: brandId,
        name,
        prompts,
        category,
      });
      setBatteries([
        {
          battery_id: result.battery_id,
          name: result.name,
          category: result.category,
          prompts: result.prompts,
          created_at: result.created_at,
        },
        ...batteries,
      ]);
      setShowForm(false);
      setName("");
      setCategory("general");
      setPrompts([]);
    } catch {
      // handled
    }
  };

  if (selectedBattery) {
    return (
      <div className="animate-fade-in">
        <PageHeader
          title={selectedBattery.name}
          subtitle={`Category: ${selectedBattery.category}`}
          actions={
            <button
              onClick={() => setSelectedBattery(null)}
              className="btn-secondary text-sm"
            >
              Back to Batteries
            </button>
          }
        />

        <div className="glass-panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-200">
              Prompts ({selectedBattery.prompts.length})
            </h2>
            <Badge variant="neutral">{selectedBattery.category}</Badge>
          </div>

          <div className="space-y-2">
            {selectedBattery.prompts.map((prompt, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
              >
                <span className="text-xs font-mono text-gray-600 mt-0.5 w-6 text-right flex-shrink-0">
                  {i + 1}
                </span>
                <p className="text-sm text-gray-300">{prompt}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 pt-4 border-t border-white/[0.06] flex items-center justify-between">
            <span className="text-xs text-gray-500">
              Created {new Date(selectedBattery.created_at).toLocaleDateString()}
            </span>
            <span className="text-xs text-gray-500">
              ID: {selectedBattery.battery_id}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Prompt Batteries"
        subtitle="Manage prompt sets for monitoring runs"
        actions={
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <Plus size={16} />
            New Battery
          </button>
        }
      />

      {/* Create Form */}
      {showForm && (
        <div className="glass-panel p-6 mb-6 animate-slide-up">
          <h2 className="text-base font-semibold text-gray-200 mb-4">
            Create Prompt Battery
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="label">Battery Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Product Discovery"
                className="input-field"
              />
            </div>
            <div>
              <label className="label">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="input-field"
              >
                <option value="general">General</option>
                <option value="product">Product</option>
                <option value="brand">Brand</option>
                <option value="competitive">Competitive</option>
                <option value="industry">Industry</option>
              </select>
            </div>
          </div>

          <div className="mb-4">
            <label className="label">Prompts</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={promptInput}
                onChange={(e) => setPromptInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addPrompt())}
                placeholder="Enter a prompt and press Enter"
                className="input-field"
              />
              <button onClick={addPrompt} className="btn-secondary px-3 flex-shrink-0">
                Add
              </button>
            </div>
          </div>

          {prompts.length > 0 && (
            <div className="space-y-2 mb-4">
              {prompts.map((p, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <span className="text-xs text-gray-500 font-mono w-5 text-right">
                    {i + 1}
                  </span>
                  <span className="flex-1 text-sm text-gray-300">{p}</span>
                  <button
                    onClick={() => removePrompt(i)}
                    className="p-1 hover:bg-white/[0.06] rounded transition-colors"
                  >
                    <X size={14} className="text-gray-500" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleCreate}
              disabled={!name.trim() || prompts.length === 0 || createBattery.isPending}
              className="btn-primary text-sm disabled:opacity-40"
            >
              {createBattery.isPending ? "Creating..." : "Create Battery"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="btn-ghost text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Battery List */}
      {batteries.length > 0 ? (
        <div className="space-y-3">
          {batteries.map((bat) => (
            <div
              key={bat.battery_id}
              onClick={() => setSelectedBattery(bat)}
              className="glass-panel-hover p-5 cursor-pointer flex items-center justify-between group"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Battery size={20} className="text-accent" />
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-200">
                    {bat.name}
                  </h3>
                  <div className="flex items-center gap-3 mt-1">
                    <Badge variant="neutral">{bat.category}</Badge>
                    <span className="text-xs text-gray-500">
                      {bat.prompts.length} prompts
                    </span>
                    <span className="text-xs text-gray-600">
                      {new Date(bat.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
              <ChevronRight
                size={16}
                className="text-gray-600 group-hover:text-gray-400 transition-colors"
              />
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Battery size={24} className="text-gray-500" />}
          title="No prompt batteries"
          description="Create your first prompt battery to start monitoring AI engine responses"
          action={{ label: "Create Battery", onClick: () => setShowForm(true) }}
        />
      )}
    </div>
  );
}
