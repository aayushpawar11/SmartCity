"use client";

import { useEffect, useState } from "react";
import type { HazardAhead } from "@/lib/routeUtils";

type Props = {
  hazard: HazardAhead;
  onReroute: () => void;
  onContinue: () => void;
};

export function HazardAlertPopup({ hazard, onReroute, onContinue }: Props) {
  const { event, milesAhead } = hazard;
  const miles = milesAhead < 0.1 ? "< 0.1" : milesAhead.toFixed(1);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const handleReroute = () => {
    setVisible(false);
    setTimeout(onReroute, 300);
  };

  const handleContinue = () => {
    setVisible(false);
    setTimeout(onContinue, 300);
  };

  return (
    <div className="absolute inset-x-0 top-0 z-[1100] flex justify-center pointer-events-none px-4 pt-4">
      <div
        className={`
          pointer-events-auto w-full max-w-md
          transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]
          ${visible ? "translate-y-0 opacity-100 scale-100" : "-translate-y-8 opacity-0 scale-95"}
        `}
      >
        <div className="relative overflow-hidden rounded-2xl bg-[#0f172a]/95 backdrop-blur-2xl ring-1 ring-amber-500/30 shadow-[0_0_60px_-15px_rgba(245,158,11,0.4)]">
          {/* Accent bar */}
          <div className="h-1 w-full bg-gradient-to-r from-amber-500 to-orange-500 relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer" />
          </div>

          <div className="p-4 space-y-3">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-xl bg-amber-500/10">
                <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126Z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-amber-300 leading-tight">
                  Hazard Ahead
                </p>
                <p className="text-xs text-[#64748b] mt-0.5 flex items-center gap-1.5">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                  {miles} miles away
                </p>
              </div>
            </div>

            {/* Description */}
            <p className="text-sm text-[#cbd5e1] leading-relaxed">{event.description}</p>

            {/* Buttons */}
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={handleReroute}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold bg-accent text-[#0a0e17] hover:bg-cyan-300 active:scale-[0.98] transition-all duration-150 shadow-[0_0_20px_-5px_rgba(34,211,238,0.4)]"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                </svg>
                Reroute
              </button>
              <button
                type="button"
                onClick={handleContinue}
                className="flex-1 rounded-xl py-2.5 text-sm font-medium text-[#94a3b8] bg-white/5 hover:bg-white/10 border border-white/10 active:scale-[0.98] transition-all duration-150"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
