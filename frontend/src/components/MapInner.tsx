"use client";

import L from "leaflet";
import { useEffect, useRef } from "react";
import type { EventItem } from "@/types/event";
import type { MapInnerProps } from "./Map";

function hazardColor(level: number): string {
  if (level >= 8) return "#dc2626";
  if (level >= 6) return "#f97316";
  if (level >= 4) return "#eab308";
  return "#22c55e";
}

export function MapInner({
  events,
  selectedEvent,
  onSelectEvent,
  loading,
  routeCoordinates,
  currentPosition,
}: MapInnerProps) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<L.CircleMarker[]>([]);
  const routeLayerRef = useRef<L.Polyline | null>(null);
  const carMarkerRef = useRef<L.CircleMarker | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const map = L.map(containerRef.current).setView([33.9, -84.3], 10);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; OpenStreetMap, CartoDB",
    }).addTo(map);
    mapRef.current = map;
    return () => {
      routeLayerRef.current?.remove();
      carMarkerRef.current?.remove();
      map.remove();
      mapRef.current = null;
      markersRef.current = [];
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    for (const ev of events) {
      const color = hazardColor(ev.hazard_level);
      const marker = L.circleMarker([ev.lat, ev.lng], {
        radius: ev.has_accident ? 12 : 8,
        fillColor: color,
        color: "#fff",
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.9,
      })
        .on("click", () => onSelectEvent(ev))
        .addTo(map);
      marker.bindTooltip(ev.description.slice(0, 40) + (ev.description.length > 40 ? "…" : ""), {
        permanent: false,
        direction: "top",
      });
      markersRef.current.push(marker);
    }
  }, [events, onSelectEvent]);

  // Route polyline
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    routeLayerRef.current?.remove();
    routeLayerRef.current = null;
    if (routeCoordinates && routeCoordinates.length >= 2) {
      const latlngs = routeCoordinates.map((c) => [c[0], c[1]] as L.LatLngTuple);
      const polyline = L.polyline(latlngs, {
        color: "#22d3ee",
        weight: 5,
        opacity: 0.95,
      }).addTo(map);
      routeLayerRef.current = polyline;
      map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
    }
  }, [routeCoordinates]);

  // Car position marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    carMarkerRef.current?.remove();
    carMarkerRef.current = null;
    if (currentPosition) {
      const marker = L.circleMarker([currentPosition[0], currentPosition[1]], {
        radius: 10,
        fillColor: "#22d3ee",
        color: "#fff",
        weight: 2,
        opacity: 1,
        fillOpacity: 1,
      }).addTo(map);
      marker.bindTooltip("You", { permanent: false, direction: "top" });
      carMarkerRef.current = marker;
    }
  }, [currentPosition]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {loading && (
        <div className="absolute top-3 right-3 glass rounded-xl px-3 py-2 text-xs font-medium text-[#94a3b8] flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
          Updating…
        </div>
      )}
    </div>
  );
}
