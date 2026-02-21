/**
 * Route geometry helpers: distance along route, point-to-route distance, find hazards ahead.
 */

export type LatLng = [number, number]; // [lat, lng]

const EARTH_RADIUS_KM = 6371;

function haversineKm(a: LatLng, b: LatLng): number {
  const [lat1, lng1] = a;
  const [lat2, lng2] = b;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const x =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(x));
}

/** Distance in km from point to line segment (haversine); returns { distKm, t (0-1 along segment) } */
export function pointToSegmentKm(
  point: LatLng,
  segStart: LatLng,
  segEnd: LatLng
): { distKm: number; t: number } {
  const steps = 15;
  let bestT = 0.5;
  let bestKm = Infinity;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const lat = segStart[0] + t * (segEnd[0] - segStart[0]);
    const lng = segStart[1] + t * (segEnd[1] - segStart[1]);
    const km = haversineKm(point, [lat, lng]);
    if (km < bestKm) {
      bestKm = km;
      bestT = t;
    }
  }
  return { distKm: bestKm, t: bestT };
}

/** Cumulative distances (km) from start of route; length = coordinates.length */
export function cumulativeDistances(coords: LatLng[]): number[] {
  const out: number[] = [0];
  for (let i = 1; i < coords.length; i++) {
    out.push(out[i - 1] + haversineKm(coords[i - 1], coords[i]));
  }
  return out;
}

/** Distance (km) from route start to the point on route closest to `point`; and that closest distance (km). */
export function pointToRouteKm(
  point: LatLng,
  coordinates: LatLng[],
  cumDist: number[]
): { distAlongRouteKm: number; distToRouteKm: number; segmentIndex: number } {
  let best = { distToRouteKm: Infinity, distAlongRouteKm: 0, segmentIndex: 0 };
  for (let i = 0; i < coordinates.length - 1; i++) {
    const { distKm, t } = pointToSegmentKm(point, coordinates[i], coordinates[i + 1]);
    const segLen = cumDist[i + 1] - cumDist[i];
    const distAlong = cumDist[i] + t * segLen;
    if (distKm < best.distToRouteKm) {
      best = { distToRouteKm: distKm, distAlongRouteKm: distAlong, segmentIndex: i };
    }
  }
  return best;
}

const MILES_PER_KM = 0.621371;
export function kmToMiles(km: number): number {
  return km * MILES_PER_KM;
}

export type HazardAhead = {
  event: { id: string; description: string; hazard_level: number; lat: number; lng: number };
  milesAhead: number;
  distToRouteKm: number;
};

/**
 * Find hazards that are (a) near the route, (b) ahead of current position, (c) within maxMilesAhead.
 */
export function hazardsAhead(
  currentIndex: number,
  coordinates: LatLng[],
  cumDist: number[],
  events: Array<{ id: string; description: string; hazard_level: number; lat: number; lng: number }>,
  options: { maxMilesAhead?: number; maxDistToRouteKm?: number; minHazardLevel?: number } = {}
): HazardAhead[] {
  const maxMilesAhead = options.maxMilesAhead ?? 5;
  const maxDistToRouteKm = options.maxDistToRouteKm ?? 0.5;
  const minHazardLevel = options.minHazardLevel ?? 4;
  const currentDistKm = cumDist[currentIndex] ?? 0;
  const results: HazardAhead[] = [];

  for (const ev of events) {
    if (ev.hazard_level < minHazardLevel) continue;
    const { distAlongRouteKm, distToRouteKm, segmentIndex } = pointToRouteKm(
      [ev.lat, ev.lng],
      coordinates,
      cumDist
    );
    if (distToRouteKm > maxDistToRouteKm) continue;
    const aheadKm = distAlongRouteKm - currentDistKm;
    if (aheadKm <= 0) continue; // behind us
    const milesAhead = kmToMiles(aheadKm);
    if (milesAhead > maxMilesAhead) continue;
    results.push({
      event: ev,
      milesAhead,
      distToRouteKm,
    });
  }
  results.sort((a, b) => a.milesAhead - b.milesAhead);
  return results;
}
