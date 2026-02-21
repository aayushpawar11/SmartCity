"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Map } from "@/components/Map";
import { SearchBar } from "@/components/SearchBar";
import { NavigationPanel } from "@/components/NavigationPanel";
import { HazardAlertPopup } from "@/components/HazardAlertPopup";
import { EnableAlertsButton } from "@/components/EnableAlertsButton";
import { Toast } from "@/components/Toast";
import type { EventItem } from "@/types/event";
import { speakAlert } from "@/lib/tts";
import { getAlertsEnabled, showBrowserNotification } from "@/lib/notifications";
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
  const [events, setEvents] = useState<EventItem[]>([]);
  const [searchResults, setSearchResults] = useState<EventItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const lastEventIds = useRef<Set<string>>(new Set());
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastTimeoutsRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Navigation
  const [routeCoordinates, setRouteCoordinates] = useState<LatLng[] | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isDriving, setIsDriving] = useState(false);
  const [destination, setDestination] = useState<LatLng | null>(null);
  const cumDistRef = useRef<number[]>([]);
  const [hazardPopup, setHazardPopup] = useState<HazardAhead | null>(null);
  const dismissedHazardsRef = useRef<Set<string>>(new Set());

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

  const fetchEvents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/events`);
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      setEvents(list);
      const currentIds = new Set(list.map((e: EventItem) => e.id));
      const alertsOn = getAlertsEnabled();
      for (const e of list) {
        if (e.hazard_level >= 6 && !lastEventIds.current.has(e.id)) {
          addToast(e);
          showBrowserNotification(
            e.hazard_level >= 8 ? "High hazard" : "Hazard reported",
            e.description
          );
          if (alertsOn) speakAlert(e);
        }
      }
      lastEventIds.current = currentIds;
    } catch (_) {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    fetchEvents();
    const t = setInterval(fetchEvents, POLL_MS);
    return () => clearInterval(t);
  }, [fetchEvents]);

  const fetchRoute = useCallback(
    async (from: LatLng, to: LatLng) => {
      const [fromLat, fromLng] = from;
      const [toLat, toLng] = to;
      const url = `${API_BASE}/route?from_lat=${fromLat}&from_lng=${fromLng}&to_lat=${toLat}&to_lng=${toLng}`;
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

  const onReroute = useCallback(() => {
    if (!routeCoordinates || !destination || cumDistRef.current.length === 0) return;
    const idx = Math.min(currentIndex, routeCoordinates.length - 1);
    const currentPos = routeCoordinates[idx];
    if (hazardPopup) dismissedHazardsRef.current.add(hazardPopup.event.id);
    setHazardPopup(null);
    fetchRoute(currentPos, destination);
  }, [routeCoordinates, destination, currentIndex, hazardPopup, fetchRoute]);

  const onContinueHazard = useCallback(() => {
    if (hazardPopup) dismissedHazardsRef.current.add(hazardPopup.event.id);
    setHazardPopup(null);
  }, [hazardPopup]);

  const onEndRoute = useCallback(() => {
    setRouteCoordinates(null);
    setCurrentIndex(0);
    setIsDriving(false);
    setDestination(null);
    setHazardPopup(null);
    dismissedHazardsRef.current.clear();
  }, []);

  // Drive simulation: advance position along route
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

  // Hazard detection along route
  useEffect(() => {
    if (!isDriving || !routeCoordinates?.length || cumDistRef.current.length === 0) return;
    const hazards = hazardsAhead(
      currentIndex,
      routeCoordinates,
      cumDistRef.current,
      events,
      { maxMilesAhead: 3, maxDistToRouteKm: 0.4, minHazardLevel: 4 }
    );
    const first = hazards.find((h) => !dismissedHazardsRef.current.has(h.event.id));
    if (first && !hazardPopup) {
      setHazardPopup(first);
      if (getAlertsEnabled()) speakAlert({
        ...first.event,
        lat: first.event.lat,
        lng: first.event.lng,
        feed_id: "",
        occurred_at: 0,
        has_police: false,
        has_accident: first.event.hazard_level >= 6,
        hazard_level: first.event.hazard_level,
        description: `Hazard ${first.milesAhead.toFixed(1)} miles ahead. ${first.event.description}`,
        image_path: null,
      });
    }
  }, [isDriving, routeCoordinates, currentIndex, events, hazardPopup]);

  const onSearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) return;
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch {
      setSearchResults([]);
    }
  }, []);

  const displayEvents = searchResults !== null ? searchResults : events;
  const currentPosition: LatLng | null =
    routeCoordinates && routeCoordinates.length > 0
      ? routeCoordinates[Math.min(currentIndex, routeCoordinates.length - 1)]
      : null;

  return (
    <main className="relative h-screen w-full flex flex-col bg-[#0a0e17]">
      <header className="flex-none glass flex flex-wrap items-center gap-4 px-5 py-3 z-10">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/20 text-accent shadow-glow-sm">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#f1f5f9]">
            SmartCity <span className="text-accent">Safety</span>
          </h1>
        </div>
        <SearchBar
          onSearch={onSearch}
          placeholder="Search events (e.g. accidents, police, flooding)"
        />
        <NavigationPanel
          onStartRoute={onStartRoute}
          isDriving={isDriving}
          onEndRoute={onEndRoute}
        />
        <EnableAlertsButton />
      </header>
      <div className="flex-1 relative min-h-0">
        <Map
          events={displayEvents}
          selectedEvent={selectedEvent}
          onSelectEvent={setSelectedEvent}
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
        {selectedEvent && (
          <EventPopup
            event={selectedEvent}
            onClose={() => setSelectedEvent(null)}
          />
        )}
        {/* In-app toasts for new hazards */}
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
    ? `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/image?path=${encodeURIComponent(event.image_path)}`
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
