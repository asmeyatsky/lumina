import { useEffect, useState } from "react";

interface ScoreGaugeProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  sublabel?: string;
  className?: string;
  animated?: boolean;
}

function getScoreColor(score: number): string {
  if (score < 40) return "#ef4444";
  if (score < 70) return "#f59e0b";
  return "#22c55e";
}

function getScoreGlow(score: number): string {
  if (score < 40) return "rgba(239, 68, 68, 0.3)";
  if (score < 70) return "rgba(245, 158, 11, 0.3)";
  return "rgba(34, 197, 94, 0.3)";
}

export default function ScoreGauge({
  score,
  size = 160,
  strokeWidth = 10,
  label,
  sublabel,
  className = "",
  animated = true,
}: ScoreGaugeProps) {
  const [displayScore, setDisplayScore] = useState(animated ? 0 : score);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedScore = Math.min(100, Math.max(0, score));
  const progress = (clampedScore / 100) * circumference;
  const color = getScoreColor(clampedScore);
  const glow = getScoreGlow(clampedScore);

  useEffect(() => {
    if (!animated) {
      setDisplayScore(clampedScore);
      return;
    }
    let start: number | null = null;
    const duration = 1200;
    const startVal = 0;
    const endVal = clampedScore;

    function step(timestamp: number) {
      if (!start) start = timestamp;
      const elapsed = timestamp - start;
      const t = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplayScore(Math.round(startVal + (endVal - startVal) * eased));
      if (t < 1) {
        requestAnimationFrame(step);
      }
    }

    requestAnimationFrame(step);
  }, [clampedScore, animated]);

  return (
    <div className={`flex flex-col items-center gap-2 ${className}`}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="transform -rotate-90"
          style={{ filter: `drop-shadow(0 0 8px ${glow})` }}
        >
          {/* Background track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={strokeWidth}
          />
          {/* Progress arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={circumference - progress}
            strokeLinecap="round"
            style={{
              transition: animated ? "stroke-dashoffset 1.2s cubic-bezier(0.22, 1, 0.36, 1)" : "none",
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-bold text-gray-100"
            style={{ fontSize: size * 0.25 }}
          >
            {displayScore}
          </span>
          {sublabel && (
            <span className="text-xs text-gray-500 mt-0.5">{sublabel}</span>
          )}
        </div>
      </div>
      {label && (
        <span className="text-sm font-medium text-gray-400">{label}</span>
      )}
    </div>
  );
}
