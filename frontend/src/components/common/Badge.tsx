import { type ReactNode } from "react";

type BadgeVariant = "success" | "warning" | "danger" | "info" | "neutral";

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: "bg-success/15 text-success border-success/20",
  warning: "bg-warning/15 text-warning border-warning/20",
  danger: "bg-danger/15 text-danger border-danger/20",
  info: "bg-accent/15 text-accent border-accent/20",
  neutral: "bg-white/[0.08] text-gray-300 border-white/[0.08]",
};

const dotStyles: Record<BadgeVariant, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-accent",
  neutral: "bg-gray-400",
};

export default function Badge({
  variant = "neutral",
  children,
  className = "",
  dot = false,
}: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2.5 py-0.5
        text-xs font-medium rounded-full border
        ${variantStyles[variant]}
        ${className}
      `}
    >
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full ${dotStyles[variant]}`} />
      )}
      {children}
    </span>
  );
}
