import { type ReactNode } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface StatCardProps {
  icon?: ReactNode;
  label: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  className?: string;
  onClick?: () => void;
}

export default function StatCard({
  icon,
  label,
  value,
  change,
  changeLabel,
  className = "",
  onClick,
}: StatCardProps) {
  const isPositive = change != null && change > 0;
  const isNegative = change != null && change < 0;
  const isNeutral = change != null && change === 0;

  return (
    <div
      className={`glass-panel p-5 ${onClick ? "cursor-pointer glass-panel-hover" : ""} ${className}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-3">
        {icon && (
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center text-accent">
            {icon}
          </div>
        )}
        {change != null && (
          <div
            className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${
              isPositive
                ? "text-success bg-success/10"
                : isNegative
                ? "text-danger bg-danger/10"
                : "text-gray-400 bg-white/[0.06]"
            }`}
          >
            {isPositive && <TrendingUp size={12} />}
            {isNegative && <TrendingDown size={12} />}
            {isNeutral && <Minus size={12} />}
            {isPositive ? "+" : ""}
            {change.toFixed(1)}%
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-gray-100 mb-1">{value}</div>
      <div className="text-sm text-gray-500">
        {label}
        {changeLabel && (
          <span className="text-gray-600 ml-1">({changeLabel})</span>
        )}
      </div>
    </div>
  );
}
