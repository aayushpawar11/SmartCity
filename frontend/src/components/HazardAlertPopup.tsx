"use client";

import type { HazardAhead } from "@/lib/routeUtils";

type Props = {
  hazard: HazardAhead;
  onReroute: () => void;
  onContinue: () => void;
};

export function HazardAlertPopup({ hazard, onReroute, onContinue }: Props) {
  const { event, milesAhead } = hazard;
  const miles = milesAhead < 0.1 ? "< 0.1" : milesAhead.toFixed(1);

  return (
    <div className="absolute left-4 right-4 top-4 z-[1000] mx-auto max-w-md animate-in">
      <div className="rounded-2xl overflow-hidden border border-amber-500/30 bg-[#0f172a]/95 backdrop-blur-xl shadow-2xl shadow-amber-500/10 ring-1 ring-amber-500/20">
        <div className="bg-gradient-to-r from-amber-500/20 to-orange-500/10 px-5 py-3 border-b border-amber-500/20">
          <p className="text-sm font-semibold text-amber-300 flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
            Hazard {miles} miles ahead
          </p>
        </div>
        <div className="p-5">
          <p className="text-[#e2e8f0] leading-relaxed mb-4">{event.description}</p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onReroute}
              className="flex-1 rounded-xl bg-accent py-3 text-sm font-semibold text-[#0a0e17] hover:bg-cyan-300 focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-[#0f172a] transition-all shadow-glow-sm"
            >
              Reroute
            </button>
            <button
              type="button"
              onClick={onContinue}
              className="flex-1 rounded-xl bg-white/10 py-3 text-sm font-medium text-[#e2e8f0] hover:bg-white/15 border border-white/10 transition-colors"
            >
              Continue
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
