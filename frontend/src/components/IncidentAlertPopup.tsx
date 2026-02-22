"use client";

import { useEffect, useState } from "react";
import type { IncidentItem } from "@/types/event";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Props = {
  incident: IncidentItem;
  onAcceptReroute: (incident: IncidentItem) => void;
  onDismiss: (incident: IncidentItem) => void;
};

const TYPE_CONFIG: Record<string, { icon: string; label: string; accent: string }> = {
  accident: {
    icon: "M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126Z",
    label: "Accident Detected",
    accent: "red",
  },
  speed_sensor: {
    icon: "M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z",
    label: "Speed Sensor Alert",
    accent: "amber",
  },
  hazard: {
    icon: "M12 9v3.75m0 0v.008M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    label: "Road Hazard",
    accent: "orange",
  },
};

function accentClasses(rating: number) {
  if (rating >= 8) return {
    ring: "ring-red-500/30",
    border: "border-red-500/20",
    bg: "bg-red-500",
    bgDim: "bg-red-500/10",
    text: "text-red-400",
    textLight: "text-red-300",
    badge: "bg-red-500/20 text-red-300 ring-red-500/30",
    bar: "from-red-500 to-rose-600",
    glow: "shadow-[0_0_60px_-15px_rgba(239,68,68,0.5)]",
  };
  if (rating >= 6) return {
    ring: "ring-orange-500/30",
    border: "border-orange-500/20",
    bg: "bg-orange-500",
    bgDim: "bg-orange-500/10",
    text: "text-orange-400",
    textLight: "text-orange-300",
    badge: "bg-orange-500/20 text-orange-300 ring-orange-500/30",
    bar: "from-orange-500 to-amber-600",
    glow: "shadow-[0_0_60px_-15px_rgba(249,115,22,0.5)]",
  };
  return {
    ring: "ring-yellow-500/30",
    border: "border-yellow-500/20",
    bg: "bg-yellow-500",
    bgDim: "bg-yellow-500/10",
    text: "text-yellow-400",
    textLight: "text-yellow-300",
    badge: "bg-yellow-500/20 text-yellow-300 ring-yellow-500/30",
    bar: "from-yellow-500 to-amber-500",
    glow: "shadow-[0_0_60px_-15px_rgba(234,179,8,0.5)]",
  };
}

export function IncidentAlertPopup({ incident, onAcceptReroute, onDismiss }: Props) {
  const [visible, setVisible] = useState(false);
  const config = TYPE_CONFIG[incident.event_type] || TYPE_CONFIG.hazard;
  const colors = accentClasses(incident.rating);
  const imgUrl = incident.image_path
    ? `${API_BASE}/image?path=${encodeURIComponent(incident.image_path)}`
    : null;

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const handleDismiss = () => {
    setVisible(false);
    setTimeout(() => onDismiss(incident), 300);
  };

  const handleReroute = () => {
    setVisible(false);
    setTimeout(() => onAcceptReroute(incident), 300);
  };

  return (
    <div className="absolute inset-x-0 top-0 z-[1100] flex justify-center pointer-events-none px-4 pt-4">
      <div
        className={`
          pointer-events-auto w-full max-w-md
          transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]
          ${visible ? "translate-y-0 opacity-100 scale-100" : "-translate-y-8 opacity-0 scale-95"}
        `}
      >
        <div
          className={`
            relative overflow-hidden rounded-2xl
            bg-[#0f172a]/95 backdrop-blur-2xl
            ring-1 ${colors.ring}
            ${colors.glow}
          `}
        >
          {/* Animated accent bar at top */}
          <div className={`h-1 w-full bg-gradient-to-r ${colors.bar} relative overflow-hidden`}>
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer" />
          </div>

          <div className="p-4 space-y-3">
            {/* Header row */}
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className={`flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-xl ${colors.bgDim}`}>
                  <svg className={`w-5 h-5 ${colors.text}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={config.icon} />
                  </svg>
                </div>
                <div className="min-w-0">
                  <p className={`text-sm font-semibold ${colors.textLight} leading-tight`}>
                    {config.label}
                  </p>
                  <p className="text-xs text-[#64748b] mt-0.5">
                    On your current route
                  </p>
                </div>
              </div>

              {/* Rating badge */}
              <div className={`flex-shrink-0 px-2.5 py-1 rounded-lg ring-1 text-xs font-bold tabular-nums ${colors.badge}`}>
                {incident.rating}/10
              </div>
            </div>

            {/* Image */}
            {imgUrl && (
              <div className="rounded-xl overflow-hidden ring-1 ring-white/10">
                <img src={imgUrl} alt="Incident" className="w-full aspect-[16/9] object-cover" />
              </div>
            )}

            {/* Description */}
            <p className="text-sm text-[#cbd5e1] leading-relaxed">
              {incident.description || incident.notification || "An incident has been detected on your route."}
            </p>

            {/* Stats row */}
            <div className="flex items-center gap-3 text-[11px] text-[#64748b]">
              <span className="flex items-center gap-1">
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${colors.bg} animate-pulse`} />
                {(incident.confidence * 100).toFixed(0)}% confidence
              </span>
              {incident.vehicles_detected > 0 && (
                <span>{incident.vehicles_detected} vehicle{incident.vehicles_detected !== 1 ? "s" : ""}</span>
              )}
              {incident.blocked_lanes > 0 && (
                <span>{incident.blocked_lanes} lane{incident.blocked_lanes !== 1 ? "s" : ""} blocked</span>
              )}
            </div>

            {/* Buttons */}
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={handleReroute}
                className={`
                  flex-1 flex items-center justify-center gap-2
                  rounded-xl py-2.5 text-sm font-semibold
                  bg-accent text-[#0a0e17]
                  hover:bg-cyan-300 active:scale-[0.98]
                  transition-all duration-150
                  shadow-[0_0_20px_-5px_rgba(34,211,238,0.4)]
                `}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                </svg>
                Reroute
              </button>
              <button
                type="button"
                onClick={handleDismiss}
                className="flex-1 rounded-xl py-2.5 text-sm font-medium text-[#94a3b8] bg-white/5 hover:bg-white/10 border border-white/10 active:scale-[0.98] transition-all duration-150"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
