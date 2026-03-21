import { Loader2 } from "lucide-react";

interface LoadingSpinnerProps {
  size?: number;
  className?: string;
  label?: string;
}

export default function LoadingSpinner({
  size = 24,
  className = "",
  label,
}: LoadingSpinnerProps) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 ${className}`}>
      <Loader2
        size={size}
        className="animate-spin text-accent"
      />
      {label && (
        <p className="text-sm text-gray-400">{label}</p>
      )}
    </div>
  );
}
