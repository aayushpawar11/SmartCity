"use client";

import { useState, useCallback, useEffect } from "react";
import {
  getAlertsEnabled,
  setAlertsEnabled,
  requestNotificationPermission,
  getNotificationPermission,
  type PermissionState,
} from "@/lib/notifications";
import { speakAlert } from "@/lib/tts";
import type { EventItem } from "@/types/event";

type Props = {
  onEnabled?: () => void;
};

function playTestAlert(): void {
  const test: EventItem = {
    id: "test",
    feed_id: "system",
    lat: 0,
    lng: 0,
    occurred_at: 0,
    has_police: false,
    has_accident: false,
    hazard_level: 6,
    description: "Alerts are on. You will hear hazard warnings when they are detected.",
    image_path: null,
  };
  speakAlert(test);
}

export function EnableAlertsButton({ onEnabled }: Props) {
  const [enabled, setEnabledState] = useState(false);
  const [permission, setPermission] = useState<PermissionState>("default");
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setEnabledState(getAlertsEnabled());
    setPermission(getNotificationPermission());
  }, []);

  const handleEnable = useCallback(async () => {
    setLoading(true);
    try {
      const perm = await requestNotificationPermission();
      setPermission(perm);
      setAlertsEnabled(true);
      setEnabledState(true);
      playTestAlert();
      onEnabled?.();
    } catch {
      setAlertsEnabled(true);
      setEnabledState(true);
      playTestAlert();
      onEnabled?.();
    } finally {
      setLoading(false);
    }
  }, [onEnabled]);

  if (!mounted) {
    return (
      <button
        type="button"
        disabled
        className="rounded-xl bg-accent/20 px-3 py-2 text-sm font-medium text-accent opacity-60 transition-all"
      >
        Enable alerts
      </button>
    );
  }

  if (enabled) {
    return (
      <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        Alerts on
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={handleEnable}
      disabled={loading}
      className="rounded-xl bg-accent/20 px-3 py-2 text-sm font-medium text-accent hover:bg-accent/30 focus:ring-2 focus:ring-accent/40 disabled:opacity-60 transition-all"
    >
      {loading ? "Enabling…" : "Enable alerts"}
    </button>
  );
}
