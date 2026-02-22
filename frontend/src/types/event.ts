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
  rating: number;
  vehicles_detected: number;
  blocked_lanes: number;
  clearance_minutes: number | null;
  image_path: string | null;
  description: string | null;
  notification: string | null;
  created_at: number;
};

export function ratingToHazardLevel(rating: number): number {
  return Math.max(1, Math.min(10, rating));
}

export function ratingColor(rating: number): string {
  if (rating >= 8) return "#dc2626";
  if (rating >= 6) return "#f97316";
  if (rating >= 4) return "#eab308";
  if (rating >= 2) return "#22c55e";
  return "#64748b";
}

export function ratingLabel(rating: number): string {
  if (rating >= 8) return "critical";
  if (rating >= 6) return "high";
  if (rating >= 4) return "moderate";
  if (rating >= 2) return "low";
  return "none";
}
