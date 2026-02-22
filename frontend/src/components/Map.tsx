"use client";

import dynamic from "next/dynamic";
import type { EventItem, IncidentItem } from "@/types/event";

export type LatLng = [number, number];

type MapProps = {
  events: EventItem[];
  incidents: IncidentItem[];
  selectedEvent: EventItem | null;
  selectedIncident: IncidentItem | null;
  onSelectEvent: (e: EventItem | null) => void;
  onSelectIncident: (i: IncidentItem | null) => void;
  loading?: boolean;
  routeCoordinates?: LatLng[] | null;
  currentPosition?: LatLng | null;
};

const MapInner = dynamic(() => import("./MapInner").then((m) => m.MapInner), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center bg-slate-900 text-slate-500">
      Loading map…
    </div>
  ),
});

export function Map(props: MapProps) {
  return <MapInner {...props} />;
}

export type MapInnerProps = MapProps;
