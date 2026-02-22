"use client";

import type { IncidentItem } from "@/types/event";
import { ratingLabel } from "@/types/event";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Props = {
  incident: IncidentItem;
  onClose: () => void;
};

function ratingStyle(rating: number): { bg: string; text: string; dot: string } {
  if (rating >= 8) return { bg: "bg-red-500/20", text: "text-red-300", dot: "bg-red-500" };
  if (rating >= 6) return { bg: "bg-orange-500/20", text: "text-orange-300", dot: "bg-orange-500" };
  if (rating >= 4) return { bg: "bg-yellow-500/20", text: "text-yellow-300", dot: "bg-yellow-500" };
  if (rating >= 2) return { bg: "bg-green-500/20", text: "text-green-300", dot: "bg-green-500" };
  return { bg: "bg-slate-500/20", text: "text-slate-300", dot: "bg-slate-500" };
}

const TYPE_LABELS: Record<string, string> = {
  accident: "Accident",
  speed_sensor: "Speed Sensor",
  hazard: "Hazard",
};

export function IncidentPopup({ incident, onClose }: Props) {
  const imgUrl = incident.image_path
    ? `${API_BASE}/image?path=${encodeURIComponent(incident.image_path)}`
    : null;

  const style = ratingStyle(incident.rating);
  const typeLabel = TYPE_LABELS[incident.event_type] || incident.event_type;

  return (
    <div className="absolute bottom-5 left-5 right-5 md:left-auto md:right-5 md:w-[400px] glass rounded-2xl shadow-2xl z-[1000] overflow-hidden animate-in border border-white/5">
      {/* Header */}
      <div className="p-4 flex justify-between items-center border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${style.bg} ${style.text} text-xs font-semibold`}>
            <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
            {incident.rating}/10
          </span>
          <span className="text-xs font-medium text-[#94a3b8]">{typeLabel}</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-[#94a3b8] hover:bg-white/10 hover:text-white transition-colors"
          aria-label="Close"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="p-4 space-y-3">
        {/* Camera frame image */}
        {imgUrl && (
          <div className="rounded-xl overflow-hidden ring-1 ring-white/10">
            <img src={imgUrl} alt="Camera frame" className="w-full aspect-video object-cover" />
          </div>
        )}

        {/* Description */}
        {incident.description && (
          <p className="text-[#e2e8f0] leading-relaxed text-sm">{incident.description}</p>
        )}

        {/* Notification banner */}
        {incident.notification && (
          <div className="rounded-xl bg-accent/10 border border-accent/20 px-3 py-2">
            <p className="text-xs font-medium text-accent">{incident.notification}</p>
          </div>
        )}

        {/* Stats grid */}
        <div className="grid grid-cols-3 gap-2">
          <StatBox label="Confidence" value={`${(incident.confidence * 100).toFixed(0)}%`} />
          <StatBox label="Vehicles" value={String(incident.vehicles_detected)} />
          <StatBox label="Blocked" value={`${incident.blocked_lanes} lane${incident.blocked_lanes !== 1 ? "s" : ""}`} />
        </div>

        {incident.clearance_minutes != null && (
          <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Est. clearance: {incident.clearance_minutes.toFixed(0)} min
          </div>
        )}

        {/* Coordinates */}
        <p className="text-[10px] text-[#475569] font-mono">
          {incident.lat.toFixed(4)}, {incident.lon.toFixed(4)} &middot; ID #{incident.id}
        </p>
      </div>
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/5 border border-white/5 px-2.5 py-2 text-center">
      <p className="text-[10px] font-medium text-[#64748b] uppercase tracking-wider">{label}</p>
      <p className="text-sm font-semibold text-[#e2e8f0] mt-0.5">{value}</p>
    </div>
  );
}
