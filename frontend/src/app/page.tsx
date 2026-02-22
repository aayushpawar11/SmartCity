"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Map } from "@/components/Map";
import { NavigationPanel } from "@/components/NavigationPanel";
import { HazardAlertPopup } from "@/components/HazardAlertPopup";
import { IncidentAlertPopup } from "@/components/IncidentAlertPopup";
import { EnableAlertsButton } from "@/components/EnableAlertsButton";
import { Toast } from "@/components/Toast";
import { IncidentPopup } from "@/components/IncidentPopup";
import type { EventItem, IncidentItem } from "@/types/event";
import { ratingToHazardLevel } from "@/types/event";
import { speakAlert } from "@/lib/tts";
import { getAlertsEnabled } from "@/lib/notifications";
import {
  cumulativeDistances,
  hazardsAhead,
  type HazardAhead,
  type LatLng,
} from "@/lib/routeUtils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const POLL_MS = 5000;
const DRIVE_TICK_MS = 2000;
const ROUTE_STEP = 3;
const TOAST_TTL_MS = 6000;

export type ToastItem = { id: string; event: EventItem };

export default function Home() {
  // Legacy events
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const lastEventIds = useRef<Set<string>>(new Set());
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastTimeoutsRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Incidents (from /process-frame pipeline)
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<IncidentItem | null>(null);
  const lastIncidentIds = useRef<Set<number>>(new Set());

  // Incident alert popup (reroute prompt)
  const [incidentAlert, setIncidentAlert] = useState<IncidentItem | null>(null);
  const dismissedAlertIds = useRef<Set<number>>(new Set());
  const alertCooldownRef = useRef(false);

  // Navigation
  const [routeCoordinates, setRouteCoordinates] = useState<LatLng[] | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isDriving, setIsDriving] = useState(false);
  const [destination, setDestination] = useState<LatLng | null>(null);
  const cumDistRef = useRef<number[]>([]);
  const [hazardPopup, setHazardPopup] = useState<HazardAhead | null>(null);
  const dismissedHazardsRef = useRef<Set<string>>(new Set());

  // ---- Toast helpers ----
  const dismissToast = useCallback((id: string) => {
    const t = toastTimeoutsRef.current[id];
    if (t) clearTimeout(t);
    delete toastTimeoutsRef.current[id];
    setToasts((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const addToast = useCallback((event: EventItem) => {
    const id = `toast-${event.id}-${Date.now()}`;
    setToasts((prev) => [...prev, { id, event }]);
    const t = setTimeout(() => dismissToast(id), TOAST_TTL_MS);
    toastTimeoutsRef.current[id] = t;
  }, [dismissToast]);

  // ---- Poll legacy events (silent — voice alerts only fire while driving) ----
  const fetchEvents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/events`);
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      setEvents(list);
      lastEventIds.current = new Set(list.map((e: EventItem) => e.id));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  // ---- Poll incidents (silent — alerts only fire while driving) ----
  const fetchIncidents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/incidents`);
      if (!res.ok) return;
      const data: IncidentItem[] = await res.json();
      setIncidents(data);
      lastIncidentIds.current = new Set(data.map((i) => i.id));
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchEvents();
    fetchIncidents();
    const t1 = setInterval(fetchEvents, POLL_MS);
    const t2 = setInterval(fetchIncidents, POLL_MS);
    return () => {
      clearInterval(t1);
      clearInterval(t2);
    };
  }, [fetchEvents, fetchIncidents]);

  // ---- Routing ----
  const fetchRoute = useCallback(
    async (from: LatLng, to: LatLng, avoidPoints?: LatLng[]) => {
      const [fromLat, fromLng] = from;
      const [toLat, toLng] = to;
      let url = `${API_BASE}/route?from_lat=${fromLat}&from_lng=${fromLng}&to_lat=${toLat}&to_lng=${toLng}`;
      if (avoidPoints && avoidPoints.length > 0) {
        const avoidStr = avoidPoints.map(([lat, lng]) => `${lat},${lng}`).join(";");
        url += `&avoid=${encodeURIComponent(avoidStr)}`;
      }
      const res = await fetch(url);
      if (!res.ok) throw new Error("Route failed");
      const data = await res.json();
      const coords: LatLng[] = data.coordinates || [];
      const cum = cumulativeDistances(coords);
      cumDistRef.current = cum;
      setRouteCoordinates(coords);
      setCurrentIndex(0);
      setDestination(to);
      setIsDriving(true);
      setHazardPopup(null);
    },
    []
  );

  const onStartRoute = useCallback(
    async (from: LatLng, to: LatLng) => {
      try {
        await fetchRoute(from, to);
      } catch {
        // could set error state
      }
    },
    [fetchRoute]
  );

  const startAlertCooldown = useCallback(() => {
    alertCooldownRef.current = true;
    setTimeout(() => { alertCooldownRef.current = false; }, 4000);
  }, []);

  const getAllAvoidPoints = useCallback((): LatLng[] => {
    const points: LatLng[] = incidents
      .filter((inc) => ratingToHazardLevel(inc.rating) >= 4)
      .map((inc) => [inc.lat, inc.lon] as LatLng);
    events
      .filter((e) => e.hazard_level >= 4)
      .forEach((e) => points.push([e.lat, e.lng] as LatLng));
    return points;
  }, [incidents, events]);

  const onReroute = useCallback(() => {
    if (!routeCoordinates || !destination || cumDistRef.current.length === 0) return;
    const idx = Math.min(currentIndex, routeCoordinates.length - 1);
    const currentPos = routeCoordinates[idx];
    if (hazardPopup) dismissedHazardsRef.current.add(hazardPopup.event.id);
    setHazardPopup(null);
    startAlertCooldown();
    fetchRoute(currentPos, destination, getAllAvoidPoints());
  }, [routeCoordinates, destination, currentIndex, hazardPopup, fetchRoute, startAlertCooldown, getAllAvoidPoints]);

  const onContinueHazard = useCallback(() => {
    if (hazardPopup) dismissedHazardsRef.current.add(hazardPopup.event.id);
    setHazardPopup(null);
    startAlertCooldown();
  }, [hazardPopup, startAlertCooldown]);

  const onAcceptIncidentReroute = useCallback(async (inc: IncidentItem) => {
    dismissedAlertIds.current.add(inc.id);
    setIncidentAlert(null);
    startAlertCooldown();

    const safeDestination: LatLng = destination || [inc.lat + 0.015, inc.lon + 0.015];
    const allAvoid = getAllAvoidPoints();

    if (routeCoordinates && routeCoordinates.length > 0) {
      const idx = Math.min(currentIndex, routeCoordinates.length - 1);
      const currentPos = routeCoordinates[idx];
      try {
        await fetchRoute(currentPos, safeDestination, allAvoid);
      } catch {
        // fallback
      }
    } else {
      try {
        await fetchRoute([inc.lat, inc.lon], safeDestination, allAvoid);
      } catch {
        // fallback
      }
    }
  }, [destination, routeCoordinates, currentIndex, fetchRoute, startAlertCooldown, getAllAvoidPoints]);

  const onDismissIncidentAlert = useCallback((inc: IncidentItem) => {
    dismissedAlertIds.current.add(inc.id);
    setIncidentAlert(null);
    startAlertCooldown();
  }, [startAlertCooldown]);

  const onEndRoute = useCallback(() => {
    setRouteCoordinates(null);
    setCurrentIndex(0);
    setIsDriving(false);
    setDestination(null);
    setHazardPopup(null);
    setIncidentAlert(null);
    dismissedHazardsRef.current.clear();
    dismissedAlertIds.current.clear();
    alertCooldownRef.current = false;
  }, []);

  // Drive simulation
  useEffect(() => {
    if (!isDriving || !routeCoordinates || routeCoordinates.length === 0) return;
    const interval = setInterval(() => {
      setCurrentIndex((i) => {
        const next = Math.min(i + ROUTE_STEP, routeCoordinates.length - 1);
        if (next >= routeCoordinates.length - 1) {
          setIsDriving(false);
        }
        return next;
      });
    }, DRIVE_TICK_MS);
    return () => clearInterval(interval);
  }, [isDriving, routeCoordinates]);

  // Hazard detection along route (combines legacy events + incidents)
  useEffect(() => {
    if (!isDriving || !routeCoordinates?.length || cumDistRef.current.length === 0) return;
    const combinedHazardSources = [
      ...events.map((e) => ({
        id: e.id,
        description: e.description,
        hazard_level: e.hazard_level,
        lat: e.lat,
        lng: e.lng,
      })),
      ...incidents.map((inc) => ({
        id: `inc-${inc.id}`,
        description: inc.notification || inc.description || inc.event_type,
        hazard_level: ratingToHazardLevel(inc.rating),
        lat: inc.lat,
        lng: inc.lon,
      })),
    ];
    const hazards = hazardsAhead(
      currentIndex,
      routeCoordinates,
      cumDistRef.current,
      combinedHazardSources,
      { maxMilesAhead: 3, maxDistToRouteKm: 0.4, minHazardLevel: 4 }
    );
    const first = hazards.find((h) => !dismissedHazardsRef.current.has(h.event.id));
    if (first && !hazardPopup) {
      setHazardPopup(first);
      if (getAlertsEnabled()) speakAlert({
        id: first.event.id,
        feed_id: "",
        lat: first.event.lat,
        lng: first.event.lng,
        occurred_at: 0,
        has_police: false,
        has_accident: first.event.hazard_level >= 6,
        hazard_level: first.event.hazard_level,
        description: `Hazard ${first.milesAhead.toFixed(1)} miles ahead. ${first.event.description}`,
        image_path: null,
      });
    }
  }, [isDriving, routeCoordinates, currentIndex, events, incidents, hazardPopup]);

  // Incident alert popup: only while driving, only for incidents ON the route, one at a time
  useEffect(() => {
    if (!isDriving || !routeCoordinates?.length || incidents.length === 0) return;
    if (incidentAlert || hazardPopup || alertCooldownRef.current) return;

    const idx = Math.min(currentIndex, routeCoordinates.length - 1);
    const [curLat, curLng] = routeCoordinates[idx];

    // ~0.005 degrees ≈ 0.5km — incident must be within this distance
    // of some point on the remaining route to be considered "on route"
    const ROUTE_PROXIMITY = 0.005;
    const remainingRoute = routeCoordinates.slice(idx);

    const eligible = incidents.filter((inc) => {
      if (ratingToHazardLevel(inc.rating) < 4) return false;
      if (dismissedAlertIds.current.has(inc.id)) return false;
      // Check if this incident is actually near the current route
      const nearRoute = remainingRoute.some(
        ([lat, lng]) =>
          Math.abs(inc.lat - lat) < ROUTE_PROXIMITY &&
          Math.abs(inc.lon - lng) < ROUTE_PROXIMITY
      );
      return nearRoute;
    });
    if (eligible.length === 0) return;

    let closest: IncidentItem | null = null;
    let closestDist = Infinity;
    for (const inc of eligible) {
      const d = Math.sqrt((inc.lat - curLat) ** 2 + (inc.lon - curLng) ** 2);
      if (d < closestDist) {
        closestDist = d;
        closest = inc;
      }
    }
    if (closest) {
      setIncidentAlert(closest);
      if (getAlertsEnabled()) {
        speakAlert({
          id: `inc-${closest.id}`,
          feed_id: "pipeline",
          lat: closest.lat,
          lng: closest.lon,
          occurred_at: closest.created_at,
          has_police: false,
          has_accident: closest.event_type === "accident",
          hazard_level: ratingToHazardLevel(closest.rating),
          description: closest.notification || closest.description || closest.event_type,
          image_path: closest.image_path,
        });
      }
    }
  }, [isDriving, routeCoordinates, currentIndex, incidents, incidentAlert, hazardPopup]);

  const displayEvents = events;
  const currentPosition: LatLng | null =
    routeCoordinates && routeCoordinates.length > 0
      ? routeCoordinates[Math.min(currentIndex, routeCoordinates.length - 1)]
      : null;

  const handleSelectIncident = useCallback((i: IncidentItem | null) => {
    setSelectedIncident(i);
    setSelectedEvent(null);
  }, []);

  const handleSelectEvent = useCallback((e: EventItem | null) => {
    setSelectedEvent(e);
    setSelectedIncident(null);
  }, []);

  return (
    <main className="relative h-screen w-full flex bg-[#0a0e17]">
      {/* Left sidebar — 1/4 width */}
      <aside className="flex-none w-[320px] h-full glass border-r border-white/5 flex flex-col z-10 overflow-y-auto">
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 pt-5 pb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/20 text-accent shadow-glow-sm">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#f1f5f9]">
            Look<span className="text-accent">Out</span>
          </h1>
        </div>

        <div className="border-t border-white/5" />

        {/* Navigation panel */}
        <div className="px-4 py-4">
          <NavigationPanel
            onStartRoute={onStartRoute}
            isDriving={isDriving}
            onEndRoute={onEndRoute}
          />
        </div>

        <div className="border-t border-white/5" />

        {/* Alerts & incident count */}
        <div className="px-5 py-4 flex items-center gap-3">
          <EnableAlertsButton />
          {incidents.length > 0 && (
            <span className="text-xs text-[#64748b]">
              {incidents.length} incident{incidents.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Footer */}
        <div className="px-5 py-3 border-t border-white/5">
          <p className="text-[11px] text-[#475569]">Routing by OSRM &middot; Maps by OpenStreetMap</p>
        </div>
      </aside>

      {/* Right side — map (3/4 width) */}
      <div className="flex-1 relative min-h-0">
        <Map
          events={isDriving ? displayEvents : []}
          incidents={isDriving ? incidents : []}
          selectedEvent={selectedEvent}
          selectedIncident={selectedIncident}
          onSelectEvent={handleSelectEvent}
          onSelectIncident={handleSelectIncident}
          loading={loading}
          routeCoordinates={routeCoordinates}
          currentPosition={currentPosition}
        />
        {hazardPopup && (
          <HazardAlertPopup
            hazard={hazardPopup}
            onReroute={onReroute}
            onContinue={onContinueHazard}
          />
        )}
        {incidentAlert && !hazardPopup && (
          <IncidentAlertPopup
            incident={incidentAlert}
            onAcceptReroute={onAcceptIncidentReroute}
            onDismiss={onDismissIncidentAlert}
          />
        )}
        {selectedIncident && (
          <IncidentPopup
            incident={selectedIncident}
            onClose={() => setSelectedIncident(null)}
          />
        )}
        {selectedEvent && !selectedIncident && (
          <EventPopup
            event={selectedEvent}
            onClose={() => setSelectedEvent(null)}
          />
        )}
        <div className="absolute bottom-5 right-5 z-[900] flex flex-col gap-2 max-w-sm">
          {toasts.map((t) => (
            <Toast key={t.id} toast={t} onDismiss={dismissToast} />
          ))}
        </div>
      </div>
    </main>
  );
}

function EventPopup({
  event,
  onClose,
}: {
  event: EventItem;
  onClose: () => void;
}) {
  const imgUrl = event.image_path
    ? `${API_BASE}/image?path=${encodeURIComponent(event.image_path)}`
    : null;

  return (
    <div className="absolute bottom-5 left-5 right-5 md:left-auto md:right-5 md:w-[380px] glass rounded-2xl shadow-2xl z-[1000] overflow-hidden animate-in border border-white/5">
      <div className="p-4 flex justify-between items-center border-b border-white/10">
        <span className="text-xs font-medium uppercase tracking-wider text-[#94a3b8]">{event.feed_id}</span>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-[#94a3b8] hover:bg-white/10 hover:text-white transition-colors"
          aria-label="Close"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>
      <div className="p-4 space-y-3">
        {imgUrl && (
          <div className="rounded-xl overflow-hidden ring-1 ring-white/10">
            <img src={imgUrl} alt="Frame" className="w-full aspect-video object-cover" />
          </div>
        )}
        <p className="text-[#e2e8f0] leading-relaxed">{event.description}</p>
        <div className="flex flex-wrap gap-2">
          {event.has_accident && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-danger/20 text-[#fda4af] text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-danger" /> Accident
            </span>
          )}
          {event.has_police && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-sky-500/20 text-sky-300 text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400" /> Police
            </span>
          )}
          <span className="text-[#64748b] text-xs">Hazard {event.hazard_level}/10</span>
        </div>
      </div>
    </div>
  );
}
