/**
 * Notification system: browser permissions, push notifications, and TTS unlock.
 * Browsers often block TTS until after a user gesture — "Enable alerts" triggers that.
 */

const ALERTS_ENABLED_KEY = "lookout-alerts-enabled";

export type PermissionState = "default" | "granted" | "denied";

export function getAlertsEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(ALERTS_ENABLED_KEY) === "true";
  } catch {
    return false;
  }
}

export function setAlertsEnabled(enabled: boolean): void {
  try {
    if (enabled) localStorage.setItem(ALERTS_ENABLED_KEY, "true");
    else localStorage.removeItem(ALERTS_ENABLED_KEY);
  } catch {
    // ignore
  }
}

export function isNotificationSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export function getNotificationPermission(): PermissionState {
  if (!isNotificationSupported()) return "denied";
  switch (Notification.permission) {
    case "granted":
      return "granted";
    case "denied":
      return "denied";
    default:
      return "default";
  }
}

/** Request browser notification permission. Call from a user click. */
export async function requestNotificationPermission(): Promise<PermissionState> {
  if (!isNotificationSupported()) return "denied";
  if (Notification.permission === "granted") return "granted";
  if (Notification.permission === "denied") return "denied";
  const result = await Notification.requestPermission();
  return result as PermissionState;
}

/** Show a browser (system) notification. Works when tab is in background. */
export function showBrowserNotification(title: string, body: string): void {
  if (typeof window === "undefined") return;
  if (!isNotificationSupported() || Notification.permission !== "granted") return;
  try {
    const n = new Notification(title, {
      body,
      icon: "/favicon.ico",
      tag: "lookout-hazard",
      requireInteraction: false,
    });
    n.onclick = () => {
      window.focus();
      n.close();
    };
    setTimeout(() => n.close(), 8000);
  } catch {
    // ignore
  }
}
