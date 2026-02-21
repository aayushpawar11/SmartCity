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
