/* Explicit per-page collection context; never stored in a cross-tab cookie. */
(function () {
  "use strict";
  const initial = new URLSearchParams(window.location.search).get("library_source") || "";
  let selected = initial;
  let caption = "";
  let catalogVideos = [];
  const availability = new Map();
  function unavailableSources() {
    return [...new Map([...availability.values()].flat().map(source => [source.id, source])).values()];
  }
  function updateCaption() {
    const partial = unavailableSources().length > 0;
    caption = partial || catalogVideos.length > 1
      ? `${catalogVideos.length} ${partial ? "available " : ""}${catalogVideos.length === 1 ? "movie" : "movies"} · ${catalogVideos.reduce((n, v) => n + (v.total_scenes || 0), 0)} saved scenes${partial ? " · incomplete library" : ""}` : "";
  }
  function observeResponse(response, path) {
    const raw = response.headers?.get("x-goodq-unavailable-sources");
    if (!response.ok || raw == null) return;
    const sources = JSON.parse(raw);
    availability.set(new URL(path, window.location.origin).pathname, sources);
    updateCaption();
    let notice = document.getElementById("library-availability");
    const unavailable = unavailableSources();
    if (!notice && unavailable.length) {
      notice = document.createElement("div");
      notice.id = "library-availability";
      notice.setAttribute("role", "status");
      notice.setAttribute("aria-live", "polite");
      notice.style.cssText = "padding:10px 16px;background:#332811;color:#ffe3a1;border-bottom:1px solid #a88438;flex-shrink:0;";
      (document.querySelector(".workspace-main") || document.body).prepend(notice);
    }
    if (notice) {
      notice.hidden = !unavailable.length;
      notice.textContent = unavailable.length
        ? `${unavailable.map(source => source.name).join(", ")} unavailable. Showing available collections only; library totals are incomplete. Reload to retry.` : "";
    }
  }
  function scoped(path, source = selected) {
    const url = new URL(path, window.location.origin);
    if (url.origin !== window.location.origin) return path;
    if (source) url.searchParams.set("library_source", source);
    return url.pathname + url.search + url.hash;
  }
  function syncNavigationLinks() {
    document.querySelectorAll('a[title="Return to Memory Explorer"], .workspace-ribbon a.ribbon-btn[href], .app-header a.nav-link[href], .app-header a.nav-back-link[href]').forEach((link) => {
      const rawHref = link.getAttribute("data-base-href") || link.getAttribute("href");
      if (rawHref && rawHref.startsWith("/ui/")) {
        if (!link.hasAttribute("data-base-href")) {
          link.setAttribute("data-base-href", rawHref);
        }
        link.href = scoped(rawHref);
      }
    });
  }
  async function initHeaderCollectionSwitcher() {
    const switcher = document.getElementById("collection-source-select");
    const pill = document.getElementById("collection-switcher-pill");
    if (!switcher || typeof fetch !== "function") return;
    try {
      const resp = await fetch("/api/system/videos");
      observeResponse(resp, "/api/system/videos");
      if (!resp.ok) return;
      const videos = await resp.json();
      if (!Array.isArray(videos) || videos.length === 0) return;
      switcher.innerHTML = "";
      const activeSource = selected || "local";
      videos.forEach((v) => {
        const opt = document.createElement("option");
        const src = v.library_source || "local";
        opt.value = src;
        opt.textContent = v.title || v.video_id || src;
        if (v.review_report_id) opt.setAttribute("data-review-report", v.review_report_id);
        if (src === activeSource) opt.selected = true;
        switcher.appendChild(opt);
      });
      unavailableSources().forEach(source => {
        const opt = document.createElement("option");
        opt.value = source.id;
        opt.textContent = `${source.name} — unavailable`;
        opt.disabled = true;
        opt.selected = source.id === activeSource;
        switcher.appendChild(opt);
      });
      if (pill) pill.hidden = false;
      switcher.addEventListener("change", () => {
        const nextSource = switcher.value === "local" ? "" : switcher.value;
        const selectedOpt = switcher.options[switcher.selectedIndex];
        const reportId = selectedOpt ? selectedOpt.getAttribute("data-review-report") : "";
        const nextUrl = new URL(window.location.href);
        if (nextSource) nextUrl.searchParams.set("library_source", nextSource);
        else nextUrl.searchParams.delete("library_source");
        if (nextUrl.searchParams.has("matches")) {
          if (reportId) nextUrl.searchParams.set("matches", reportId);
          else nextUrl.searchParams.delete("matches");
        }
        window.location.assign(nextUrl.pathname + nextUrl.search + nextUrl.hash);
      });
    } catch (_) {}
  }
  window.GoodQLibrary = {
    observeResponse,
    get source() { return selected; },
    get caption() { return caption; },
    url: scoped,
    catalog(videos) {
      catalogVideos = videos;
      updateCaption();
    },
    select(video) {
      selected = video.library_source || initial;
      const review = document.getElementById("identity-review-link");
      if (review) {
        const params = new URLSearchParams();
        if (video.review_report_id) params.set("matches", video.review_report_id);
        review.href = scoped(`/ui/identity_workbench/?${params}`);
      }
      syncNavigationLinks();
    },
  };
  syncNavigationLinks();
  initHeaderCollectionSwitcher();
})();
