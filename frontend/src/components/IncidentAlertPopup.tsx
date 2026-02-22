"use client";

import type { IncidentItem } from "@/types/event";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Props = {
  incident: IncidentItem;
  onAcceptReroute: (incident: IncidentItem) => void;
  onDismiss: (incident: IncidentItem) => void;
};

const TYPE_ICONS: Record<string, string> = {
  accident: "🚗",
  speed_sensor: "📡",
  hazard: "⚠️",
};

const TYPE_LABELS: Record<string, string> = {
  accident: "Accident Detected",
  speed_sensor: "Speed Sensor Ahead",
  hazard: "Road Hazard Detected",
};

function ratingBorderColor(rating: number): string {
  if (rating >= 8) return "border-red-500/40 shadow-red-500/20";
  if (rating >= 6) return "border-orange-500/40 shadow-orange-500/20";
  return "border-yellow-500/40 shadow-yellow-500/20";
}

function ratingGradient(rating: number): string {
  if (rating >= 8) return "from-red-500/20 to-red-900/10";
  if (rating >= 6) return "from-orange-500/20 to-orange-900/10";
  return "from-yellow-500/20 to-yellow-900/10";
}

function ratingTextColor(rating: number): string {
  if (rating >= 8) return "text-red-300";
  if (rating >= 6) return "text-orange-300";
  return "text-yellow-300";
}

export function IncidentAlertPopup({ incident, onAcceptReroute, onDismiss }: Props) {
  const icon = TYPE_ICONS[incident.event_type] || "⚠️";
  const label = TYPE_LABELS[incident.event_type] || "Incident Detected";
  const imgUrl = incident.image_path
    ? `${API_BASE}/image?path=${encodeURIComponent(incident.image_path)}`
    : null;

  return (
    <div className="absolute left-4 right-4 top-4 z-[1100] mx-auto max-w-lg animate-in">
      <div
        className={`rounded-2xl overflow-hidden border ${ratingBorderColor(incident.rating)} bg-[#0f172a]/95 backdrop-blur-xl shadow-2xl ring-1 ring-white/5`}
      >
        {/* Header */}
        <div className={`bg-gradient-to-r ${ratingGradient(incident.rating)} px-5 py-3 border-b border-white/10`}>
          <div className="flex items-center justify-between">
            <p className={`text-sm font-semibold ${ratingTextColor(incident.rating)} flex items-center gap-2`}>
              <span className="text-lg">{icon}</span>
              {label}
            </p>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-md bg-white/10 ${ratingTextColor(incident.rating)}`}>
              {incident.rating}/10
            </span>
          </div>
        </div>

        <div className="p-4 space-y-3">
          {/* Image */}
          {imgUrl && (
            <div className="rounded-xl overflow-hidden ring-1 ring-white/10">
              <img src={imgUrl} alt="Incident" className="w-full aspect-video object-cover" />
            </div>
          )}

          {/* Description */}
          <p className="text-[#e2e8f0] leading-relaxed text-sm">
            {incident.description || incident.notification || "An incident has been detected on your route."}
          </p>

          {/* Notification banner */}
          {incident.notification && (
            <div className={`rounded-xl bg-white/5 border border-white/10 px-3 py-2`}>
              <p className={`text-xs font-medium ${ratingTextColor(incident.rating)}`}>
                {incident.notification}
              </p>
            </div>
          )}

          {/* Stats */}
          <div className="flex items-center gap-4 text-xs text-[#94a3b8]">
            <span>Confidence: {(incident.confidence * 100).toFixed(0)}%</span>
            {incident.vehicles_detected > 0 && (
              <span>{incident.vehicles_detected} vehicle{incident.vehicles_detected !== 1 ? "s" : ""}</span>
            )}
            {incident.blocked_lanes > 0 && (
              <span>{incident.blocked_lanes} lane{incident.blocked_lanes !== 1 ? "s" : ""} blocked</span>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={() => onAcceptReroute(incident)}
              className="flex-1 rounded-xl bg-accent py-3 text-sm font-semibold text-[#0a0e17] hover:bg-cyan-300 focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-[#0f172a] transition-all shadow-glow-sm"
            >
              Accept Reroute
            </button>
            <button
              type="button"
              onClick={() => onDismiss(incident)}
              className="flex-1 rounded-xl bg-white/10 py-3 text-sm font-medium text-[#e2e8f0] hover:bg-white/15 border border-white/10 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
