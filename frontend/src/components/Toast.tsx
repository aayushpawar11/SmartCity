"use client";

import type { EventItem } from "@/types/event";

type ToastItem = {
  id: string;
  event: EventItem;
};

type Props = {
  toast: ToastItem;
  onDismiss: (id: string) => void;
};

export function Toast({ toast, onDismiss }: Props) {
  const { id, event } = toast;
  const isHigh = event.hazard_level >= 8;

  return (
    <div
      className="flex items-start gap-3 rounded-xl border border-white/10 bg-[#0f172a]/95 backdrop-blur-xl p-3 shadow-lg animate-in min-w-[280px] max-w-sm"
      role="alert"
    >
      <span
        className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${
          isHigh ? "bg-danger" : "bg-amber-400"
        }`}
      />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-[#94a3b8] uppercase tracking-wider">
          {isHigh ? "High hazard" : "Hazard reported"}
        </p>
        <p className="text-sm text-[#e2e8f0] mt-0.5 line-clamp-2">{event.description}</p>
      </div>
      <button
        type="button"
        onClick={() => onDismiss(id)}
        className="shrink-0 rounded p-1 text-[#64748b] hover:bg-white/10 hover:text-[#e2e8f0]"
        aria-label="Dismiss"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
