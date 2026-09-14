/* 산불지킴이 / WildfireGuardian — minimal service worker.
 * Caches the app shell, plus the LAST /v1/situation and /v1/config JSON so the
 * app can still show the most recent known situation when offline.
 * The cached situation is always re-requested first (network-first): the app
 * never prefers stale data when fresh data is reachable.
 */
const SHELL_CACHE = "wfg-shell-v1";
const DATA_CACHE = "wfg-data-v1";
const SHELL_URLS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icons/icon.svg",
  "/icons/icon-192.svg",
  "/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== SHELL_CACHE && k !== DATA_CACHE)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;

  // Last-situation cache: network first, fall back to the last good copy.
  if (url.pathname === "/v1/situation" || url.pathname === "/v1/config") {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches
              .open(DATA_CACHE)
              .then((cache) => cache.put(url.pathname, copy));
          }
          return res;
        })
        .catch(() =>
          caches
            .open(DATA_CACHE)
            .then((cache) => cache.match(url.pathname))
            .then(
              (hit) =>
                hit ||
                new Response(
                  JSON.stringify({
                    error: "offline",
                    detail_ko: "인터넷 연결이 없습니다.",
                    detail_en: "No internet connection.",
                  }),
                  {
                    status: 503,
                    headers: { "Content-Type": "application/json; charset=utf-8" },
                  },
                ),
            ),
        ),
    );
    return;
  }

  // Never cache other live API endpoints (incl. /v1/billing/*) or SSE.
  if (url.pathname.startsWith("/v1/")) return;

  // Navigations (the HTML shell): network first so a newly deployed app is
  // picked up, falling back to the cached shell when offline.
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches
              .open(SHELL_CACHE)
              .then((cache) => cache.put("/index.html", copy));
          }
          return res;
        })
        .catch(() =>
          caches
            .match("/index.html")
            .then((hit) => hit || caches.match("/")),
        ),
    );
    return;
  }

  // Static assets: cache first, then network (and backfill same-origin assets;
  // Vite asset filenames are content-hashed, so stale entries are never served).
  event.respondWith(
    caches.match(event.request).then(
      (hit) =>
        hit ||
        fetch(event.request).then((res) => {
          if (res.ok && url.origin === self.location.origin) {
            const copy = res.clone();
            caches
              .open(SHELL_CACHE)
              .then((cache) => cache.put(event.request, copy));
          }
          return res;
        }),
    ),
  );
});
