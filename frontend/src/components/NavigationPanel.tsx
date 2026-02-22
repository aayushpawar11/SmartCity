"use client";

import { useState } from "react";

const DEFAULT_FROM = "Lawrenceville, GA";
const DEFAULT_TO = "Atlanta, GA";

type Props = {
  onStartRoute: (from: [number, number], to: [number, number]) => void;
  isDriving: boolean;
  onEndRoute: () => void;
};

function parseCoord(s: string): [number, number] | null {
  const parts = s.trim().split(/[\s,]+/).map(Number);
  if (parts.length >= 2 && !parts.some(isNaN)) return [parts[0], parts[1]];
  return null;
}

async function geocode(query: string): Promise<[number, number] | null> {
  const coord = parseCoord(query);
  if (coord) return coord;

  try {
    const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`;
    const res = await fetch(url, {
      headers: { "User-Agent": "SmartCity-Safety/1.0" },
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.length === 0) return null;
    return [parseFloat(data[0].lat), parseFloat(data[0].lon)];
  } catch {
    return null;
  }
}

export function NavigationPanel({ onStartRoute, isDriving, onEndRoute }: Props) {
  const [from, setFrom] = useState(DEFAULT_FROM);
  const [to, setTo] = useState(DEFAULT_TO);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleStart() {
    setError("");
    setLoading(true);
    try {
      const [fromCoord, toCoord] = await Promise.all([geocode(from), geocode(to)]);
      if (!fromCoord) {
        setError(`Could not find "${from}"`);
        return;
      }
      if (!toCoord) {
        setError(`Could not find "${to}"`);
        return;
      }
      onStartRoute(fromCoord, toCoord);
    } catch {
      setError("Geocoding failed — try coordinates instead");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="glass rounded-2xl p-4 min-w-[280px] shadow-xl border-white/5">
      <div className="flex items-center gap-2 mb-3">
        <div className="h-8 w-8 rounded-lg bg-accent/20 flex items-center justify-center">
          <svg className="h-4 w-4 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-[#f1f5f9]">Navigate</h3>
      </div>
      {!isDriving ? (
        <>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#94a3b8]">From</label>
            <input
              type="text"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              placeholder="e.g. Georgia Tech, Atlanta"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-[#f1f5f9] placeholder-[#64748b] focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
            />
          </div>
          <div className="space-y-1.5 mt-3">
            <label className="text-xs font-medium text-[#94a3b8]">To</label>
            <input
              type="text"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="e.g. Hartsfield-Jackson Airport"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-[#f1f5f9] placeholder-[#64748b] focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
            />
          </div>
          {error && <p className="mt-2 text-xs text-danger">{error}</p>}
          <button
            type="button"
            onClick={handleStart}
            disabled={loading}
            className="mt-4 w-full rounded-xl bg-accent py-3 text-sm font-semibold text-[#0a0e17] hover:bg-cyan-300 focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-[#0f172a] transition-all shadow-glow-sm disabled:opacity-50"
          >
            {loading ? "Finding route…" : "Get directions"}
          </button>
        </>
      ) : (
        <div className="flex items-center justify-between pt-1">
          <span className="flex items-center gap-2 text-sm text-[#94a3b8]">
            <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
            Driving…
          </span>
          <button
            type="button"
            onClick={onEndRoute}
            className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-[#e2e8f0] hover:bg-white/15 transition-colors"
          >
            End
          </button>
        </div>
      )}
    </div>
  );
}
