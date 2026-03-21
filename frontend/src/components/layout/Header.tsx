import { useState, useRef, useEffect } from "react";
import { Bell, ChevronDown, User } from "lucide-react";
import Badge from "@/components/common/Badge";

interface HeaderProps {
  currentBrandId: string;
  brands: Array<{ id: string; name: string }>;
  onBrandChange: (brandId: string) => void;
  avsScore?: number | null;
  notificationCount?: number;
}

export default function Header({
  currentBrandId,
  brands,
  onBrandChange,
  avsScore,
  notificationCount = 0,
}: HeaderProps) {
  const [brandDropdownOpen, setBrandDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const currentBrand = brands.find((b) => b.id === currentBrandId);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setBrandDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const scoreColor =
    avsScore == null
      ? "text-gray-500"
      : avsScore >= 70
      ? "text-success"
      : avsScore >= 40
      ? "text-warning"
      : "text-danger";

  return (
    <header className="h-16 border-b border-white/[0.06] bg-card/40 backdrop-blur-sm flex items-center justify-between px-6">
      {/* Brand selector */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setBrandDropdownOpen(!brandDropdownOpen)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/[0.04] transition-colors"
        >
          <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center">
            <span className="text-xs font-bold text-accent">
              {currentBrand?.name.charAt(0).toUpperCase() || "?"}
            </span>
          </div>
          <span className="text-sm font-medium text-gray-200">
            {currentBrand?.name || "Select Brand"}
          </span>
          <ChevronDown size={14} className="text-gray-500" />
        </button>
        {brandDropdownOpen && (
          <div className="absolute top-full left-0 mt-1 w-56 bg-card border border-white/[0.08] rounded-lg shadow-xl py-1 z-50 animate-fade-in">
            {brands.map((brand) => (
              <button
                key={brand.id}
                onClick={() => {
                  onBrandChange(brand.id);
                  setBrandDropdownOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                  brand.id === currentBrandId
                    ? "text-accent bg-accent/10"
                    : "text-gray-300 hover:bg-white/[0.04]"
                }`}
              >
                {brand.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right section */}
      <div className="flex items-center gap-4">
        {/* AVS Score Badge */}
        {avsScore != null && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
            <span className="text-xs text-gray-500 font-medium">AVS</span>
            <span className={`text-sm font-bold ${scoreColor}`}>
              {avsScore.toFixed(0)}
            </span>
          </div>
        )}

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-white/[0.04] transition-colors">
          <Bell size={18} className="text-gray-400" />
          {notificationCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-danger rounded-full text-[10px] font-bold text-white flex items-center justify-center">
              {notificationCount > 9 ? "9+" : notificationCount}
            </span>
          )}
        </button>

        {/* User avatar */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary-400 flex items-center justify-center border border-white/[0.08]">
            <User size={16} className="text-gray-300" />
          </div>
        </div>
      </div>
    </header>
  );
}
