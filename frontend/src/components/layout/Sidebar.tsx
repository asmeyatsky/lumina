import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Activity,
  GitBranch,
  Zap,
  Radio,
  Brain,
  Settings,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
} from "lucide-react";

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
  module?: string;
}

const navItems: NavItem[] = [
  {
    path: "/",
    label: "Dashboard",
    icon: <LayoutDashboard size={20} />,
  },
  {
    path: "/pulse",
    label: "PULSE",
    icon: <Activity size={20} />,
    module: "pulse",
  },
  {
    path: "/graph",
    label: "GRAPH",
    icon: <GitBranch size={20} />,
    module: "graph",
  },
  {
    path: "/beam",
    label: "BEAM",
    icon: <Zap size={20} />,
    module: "beam",
  },
  {
    path: "/signal",
    label: "SIGNAL",
    icon: <Radio size={20} />,
    module: "signal",
  },
  {
    path: "/intelligence",
    label: "Intelligence",
    icon: <Brain size={20} />,
    module: "intelligence",
  },
];

const bottomItems: NavItem[] = [
  {
    path: "/settings",
    label: "Settings",
    icon: <Settings size={20} />,
  },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <aside
      className={`
        fixed left-0 top-0 h-screen z-40
        bg-card/60 backdrop-blur-xl border-r border-white/[0.06]
        flex flex-col
        transition-all duration-300 ease-in-out
        ${collapsed ? "w-[68px]" : "w-[240px]"}
      `}
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-blue-500 flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">L</span>
          </div>
          {!collapsed && (
            <div className="flex flex-col overflow-hidden">
              <span className="text-sm font-bold text-gray-100 tracking-wide">
                LUMINA
              </span>
              <span className="text-[10px] text-gray-500 tracking-widest uppercase">
                AI Visibility
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={`
              flex items-center gap-3 px-3 py-2.5 rounded-lg
              text-sm font-medium transition-all duration-150
              group relative
              ${
                isActive(item.path)
                  ? "bg-accent/10 text-accent"
                  : "text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]"
              }
            `}
          >
            <span className="flex-shrink-0">{item.icon}</span>
            {!collapsed && (
              <span className="truncate">{item.label}</span>
            )}
            {collapsed && (
              <div className="absolute left-full ml-2 px-2 py-1 bg-card border border-white/[0.08] rounded-md text-xs text-gray-200 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                {item.label}
              </div>
            )}
            {isActive(item.path) && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-r" />
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="py-3 px-3 border-t border-white/[0.06] space-y-1">
        {bottomItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={`
              flex items-center gap-3 px-3 py-2.5 rounded-lg
              text-sm font-medium transition-all duration-150
              ${
                isActive(item.path)
                  ? "bg-accent/10 text-accent"
                  : "text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]"
              }
            `}
          >
            <span className="flex-shrink-0">{item.icon}</span>
            {!collapsed && <span className="truncate">{item.label}</span>}
          </NavLink>
        ))}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-sm font-medium text-gray-500 hover:text-gray-300 hover:bg-white/[0.04] transition-colors"
        >
          {collapsed ? (
            <ChevronRight size={20} />
          ) : (
            <>
              <ChevronLeft size={20} />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
