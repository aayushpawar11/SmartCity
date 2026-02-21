"use client";

import { useState } from "react";

const DEFAULT_FROM = "37.7749,-122.4194";
const DEFAULT_TO = "37.7849,-122.4094";

type Props = {
  onStartRoute: (from: [number, number], to: [number, number]) => void;
  isDriving: boolean;
  onEndRoute: () => void;
};

export function NavigationPanel({ onStartRoute, isDriving, onEndRoute }: Props) {
  const [from, setFrom] = useState(DEFAULT_FROM);
  const [to, setTo] = useState(DEFAULT_TO);
  const [error, setError] = useState("");

  function parseCoord(s: string): [number, number] | null {
    const parts = s.trim().split(/[\s,]+/).map(Number);
    if (parts.length >= 2 && !parts.some(isNaN)) return [parts[0], parts[1]];
    return null;
  }

  function handleStart() {
    setError("");
    const fromCoord = parseCoord(from);
    const toCoord = parseCoord(to);
    if (!fromCoord) {
      setError("Invalid From (use lat,lng e.g. 37.77,-122.42)");
      return;
    }
    if (!toCoord) {
      setError("Invalid To (use lat,lng e.g. 37.78,-122.41)");
      return;
    }
    onStartRoute(fromCoord, toCoord);
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
            <label className="text-xs font-medium text-[#94a3b8]">From (lat, lng)</label>
            <input
              type="text"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              placeholder="37.77, -122.42"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-[#f1f5f9] placeholder-[#64748b] focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
            />
          </div>
          <div className="space-y-1.5 mt-3">
            <label className="text-xs font-medium text-[#94a3b8]">To (lat, lng)</label>
            <input
              type="text"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="37.78, -122.41"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-[#f1f5f9] placeholder-[#64748b] focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
            />
          </div>
          {error && <p className="mt-2 text-xs text-danger">{error}</p>}
          <button
            type="button"
            onClick={handleStart}
            className="mt-4 w-full rounded-xl bg-accent py-3 text-sm font-semibold text-[#0a0e17] hover:bg-cyan-300 focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-[#0f172a] transition-all shadow-glow-sm"
          >
            Get directions
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
