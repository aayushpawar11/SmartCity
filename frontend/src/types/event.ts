export type EventItem = {
  id: string;
  feed_id: string;
  lat: number;
  lng: number;
  occurred_at: number;
  has_police: boolean;
  has_accident: boolean;
  hazard_level: number;
  description: string;
  image_path: string | null;
  created_at?: number;
};

export type IncidentItem = {
  id: number;
  event_type: string;
  confidence: number;
  timestamp: string;
  lat: number;
  lon: number;
  severity: string;
  vehicles_detected: number;
  blocked_lanes: number;
  clearance_minutes: number | null;
  image_path: string | null;
  description: string | null;
  notification: string | null;
  created_at: number;
};

export function severityToHazardLevel(severity: string): number {
  switch (severity) {
    case "critical": return 10;
    case "high": return 8;
    case "moderate": return 6;
    case "low": return 3;
    case "none": return 1;
    default: return 5;
  }
}

export function severityColor(severity: string): string {
  switch (severity) {
    case "critical": return "#dc2626";
    case "high": return "#f97316";
    case "moderate": return "#eab308";
    case "low": return "#22c55e";
    case "none": return "#64748b";
    default: return "#94a3b8";
  }
}
