import api from "./api";
import { store } from "../store";

const INTERVAL_MS = 10 * 60 * 1000;

let lastRefresh = 0;
let inFlight: Promise<unknown> | null = null;

async function renew(): Promise<void> {
  if (store.getState().auth.authState !== "authenticated") return;
  if (Date.now() - lastRefresh < INTERVAL_MS) return;
  if (inFlight) return;
  try {
    inFlight = api.post("/auth/refresh");
    await inFlight;
    lastRefresh = Date.now();
  } catch {
    // 401 handling belongs to the api interceptor
  } finally {
    inFlight = null;
  }
}

setInterval(() => {
  void renew();
}, INTERVAL_MS);

window.addEventListener("focus", () => {
  void renew();
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") void renew();
});
