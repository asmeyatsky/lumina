import { useState } from "react";
import { Save, Plus, Trash2, Key, Users, Bell, Building } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import Badge from "@/components/common/Badge";

export default function Settings() {
  const [brandName, setBrandName] = useState("My Brand");
  const [competitors, setCompetitors] = useState<string[]>(["Competitor A", "Competitor B"]);
  const [verticals, setVerticals] = useState<string[]>(["Technology", "SaaS"]);
  const [newCompetitor, setNewCompetitor] = useState("");
  const [newVertical, setNewVertical] = useState("");
  const [activeSection, setActiveSection] = useState("brand");

  // Alert thresholds
  const [citationThreshold, setCitationThreshold] = useState(20);
  const [avsDropThreshold, setAvsDropThreshold] = useState(5);
  const [geoScoreThreshold, setGeoScoreThreshold] = useState(50);

  // API keys (masked)
  const [apiKeys] = useState([
    { id: "key-1", name: "Production", prefix: "lum_prod_****", created: "2025-11-15" },
    { id: "key-2", name: "Staging", prefix: "lum_stg_****", created: "2025-12-01" },
  ]);

  // Team members
  const [teamMembers] = useState([
    { id: "u1", name: "Alice Johnson", email: "alice@example.com", role: "Admin" },
    { id: "u2", name: "Bob Smith", email: "bob@example.com", role: "Editor" },
    { id: "u3", name: "Carol White", email: "carol@example.com", role: "Viewer" },
  ]);

  const sections = [
    { key: "brand", label: "Brand", icon: <Building size={16} /> },
    { key: "alerts", label: "Alerts", icon: <Bell size={16} /> },
    { key: "api-keys", label: "API Keys", icon: <Key size={16} /> },
    { key: "team", label: "Team", icon: <Users size={16} /> },
  ];

  const addCompetitor = () => {
    if (newCompetitor.trim() && !competitors.includes(newCompetitor.trim())) {
      setCompetitors([...competitors, newCompetitor.trim()]);
      setNewCompetitor("");
    }
  };

  const addVertical = () => {
    if (newVertical.trim() && !verticals.includes(newVertical.trim())) {
      setVerticals([...verticals, newVertical.trim()]);
      setNewVertical("");
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Settings"
        subtitle="Configure your LUMINA platform"
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Section Navigation */}
        <div className="glass-panel p-3">
          <nav className="space-y-0.5">
            {sections.map((sec) => (
              <button
                key={sec.key}
                onClick={() => setActiveSection(sec.key)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  activeSection === sec.key
                    ? "bg-accent/10 text-accent"
                    : "text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]"
                }`}
              >
                {sec.icon}
                {sec.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
          {/* Brand Configuration */}
          {activeSection === "brand" && (
            <div className="glass-panel p-6 animate-fade-in">
              <h2 className="text-base font-semibold text-gray-200 mb-6">
                Brand Configuration
              </h2>

              <div className="space-y-6">
                <div>
                  <label className="label">Brand Name</label>
                  <input
                    type="text"
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    className="input-field max-w-md"
                  />
                </div>

                <div>
                  <label className="label">Competitors</label>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {competitors.map((c, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-gray-300"
                      >
                        {c}
                        <button
                          onClick={() =>
                            setCompetitors(competitors.filter((_, idx) => idx !== i))
                          }
                          className="p-0.5 hover:text-danger transition-colors"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2 max-w-md">
                    <input
                      type="text"
                      value={newCompetitor}
                      onChange={(e) => setNewCompetitor(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCompetitor())}
                      placeholder="Add competitor"
                      className="input-field"
                    />
                    <button onClick={addCompetitor} className="btn-secondary px-3 flex-shrink-0">
                      <Plus size={16} />
                    </button>
                  </div>
                </div>

                <div>
                  <label className="label">Verticals</label>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {verticals.map((v, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-gray-300"
                      >
                        {v}
                        <button
                          onClick={() =>
                            setVerticals(verticals.filter((_, idx) => idx !== i))
                          }
                          className="p-0.5 hover:text-danger transition-colors"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2 max-w-md">
                    <input
                      type="text"
                      value={newVertical}
                      onChange={(e) => setNewVertical(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addVertical())}
                      placeholder="Add vertical"
                      className="input-field"
                    />
                    <button onClick={addVertical} className="btn-secondary px-3 flex-shrink-0">
                      <Plus size={16} />
                    </button>
                  </div>
                </div>

                <div className="pt-4 border-t border-white/[0.06]">
                  <button className="btn-primary flex items-center gap-2 text-sm">
                    <Save size={14} />
                    Save Changes
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Alert Thresholds */}
          {activeSection === "alerts" && (
            <div className="glass-panel p-6 animate-fade-in">
              <h2 className="text-base font-semibold text-gray-200 mb-6">
                Alert Thresholds
              </h2>

              <div className="space-y-6 max-w-lg">
                <div>
                  <label className="label">
                    Citation Rate Drop Threshold: {citationThreshold}%
                  </label>
                  <p className="text-xs text-gray-600 mb-2">
                    Alert when citation rate drops below this percentage
                  </p>
                  <input
                    type="range"
                    min="5"
                    max="50"
                    value={citationThreshold}
                    onChange={(e) => setCitationThreshold(parseInt(e.target.value))}
                    className="w-full accent-accent"
                  />
                  <div className="flex justify-between text-xs text-gray-600 mt-1">
                    <span>5%</span>
                    <span>50%</span>
                  </div>
                </div>

                <div>
                  <label className="label">
                    AVS Score Drop Alert: {avsDropThreshold} pts
                  </label>
                  <p className="text-xs text-gray-600 mb-2">
                    Alert when AVS drops by more than this many points
                  </p>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    value={avsDropThreshold}
                    onChange={(e) => setAvsDropThreshold(parseInt(e.target.value))}
                    className="w-full accent-accent"
                  />
                  <div className="flex justify-between text-xs text-gray-600 mt-1">
                    <span>1 pt</span>
                    <span>20 pts</span>
                  </div>
                </div>

                <div>
                  <label className="label">
                    GEO Score Threshold: {geoScoreThreshold}
                  </label>
                  <p className="text-xs text-gray-600 mb-2">
                    Flag content assets scoring below this GEO score
                  </p>
                  <input
                    type="range"
                    min="20"
                    max="80"
                    value={geoScoreThreshold}
                    onChange={(e) => setGeoScoreThreshold(parseInt(e.target.value))}
                    className="w-full accent-accent"
                  />
                  <div className="flex justify-between text-xs text-gray-600 mt-1">
                    <span>20</span>
                    <span>80</span>
                  </div>
                </div>

                <div className="pt-4 border-t border-white/[0.06]">
                  <button className="btn-primary flex items-center gap-2 text-sm">
                    <Save size={14} />
                    Save Thresholds
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* API Keys */}
          {activeSection === "api-keys" && (
            <div className="glass-panel p-6 animate-fade-in">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-base font-semibold text-gray-200">
                  API Keys
                </h2>
                <button className="btn-primary flex items-center gap-2 text-sm">
                  <Plus size={14} />
                  Create Key
                </button>
              </div>

              <div className="space-y-3">
                {apiKeys.map((key) => (
                  <div
                    key={key.id}
                    className="flex items-center justify-between p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                  >
                    <div className="flex items-center gap-4">
                      <Key size={16} className="text-gray-500" />
                      <div>
                        <span className="text-sm font-medium text-gray-200">
                          {key.name}
                        </span>
                        <p className="text-xs text-gray-500 font-mono mt-0.5">
                          {key.prefix}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-600">
                        Created {key.created}
                      </span>
                      <button className="btn-danger text-xs px-2 py-1">
                        Revoke
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Team Members */}
          {activeSection === "team" && (
            <div className="glass-panel p-6 animate-fade-in">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-base font-semibold text-gray-200">
                  Team Members
                </h2>
                <button className="btn-primary flex items-center gap-2 text-sm">
                  <Plus size={14} />
                  Invite Member
                </button>
              </div>

              <div className="space-y-3">
                {teamMembers.map((member) => (
                  <div
                    key={member.id}
                    className="flex items-center justify-between p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center">
                        <span className="text-xs font-bold text-accent">
                          {member.name
                            .split(" ")
                            .map((n) => n[0])
                            .join("")}
                        </span>
                      </div>
                      <div>
                        <span className="text-sm font-medium text-gray-200">
                          {member.name}
                        </span>
                        <p className="text-xs text-gray-500">{member.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge
                        variant={
                          member.role === "Admin"
                            ? "info"
                            : member.role === "Editor"
                            ? "success"
                            : "neutral"
                        }
                      >
                        {member.role}
                      </Badge>
                      <button className="btn-ghost text-xs">Edit</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
