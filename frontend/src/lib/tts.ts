/**
 * Voice alerts: FREE Web Speech API (no API key).
 * Optional: use ElevenLabs when ELEVENLABS_API_KEY is set (see backend or env).
 */
import type { EventItem } from "@/types/event";

export function speakAlert(event: EventItem): void {
  if (typeof window === "undefined") return;
  const level = event.hazard_level;
  const prefix =
    level >= 8
      ? "Caution. High hazard ahead. "
      : level >= 6
        ? "Hazard detected. "
        : "";
  const text = `${prefix}${event.description}. Please reroute if possible.`;
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 0.9;
    u.pitch = 1;
    window.speechSynthesis.speak(u);
  } catch {
    // ignore
  }
}
