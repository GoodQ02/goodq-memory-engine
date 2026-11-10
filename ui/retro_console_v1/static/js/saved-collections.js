(async function () {
  "use strict";
  const menu = document.getElementById("saved-collections");
  const links = document.getElementById("saved-collections-links");
  if (!menu || !links) return;
  try {
    const response = await fetch("/api/system/saved-collections");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const { collections } = await response.json();
    for (const collection of collections) {
      const row = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = collection.name;
      row.appendChild(name);
      for (const [key, label, path] of [
        ["retro_url", "Retro", "/ui/retro_console_v1/"],
        ["identity_url", "People / review", "/ui/identity_workbench/"],
      ]) {
        const url = new URL(collection[key]);
        if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
            || url.username || url.password || url.pathname !== path || !url.port || url.hash) {
          throw new Error("Invalid saved movie address");
        }
        const link = document.createElement("a");
        link.href = url.href;
        link.textContent = label;
        link.setAttribute("aria-label", `${collection.name}: ${label}`);
        row.appendChild(link);
      }
      links.appendChild(row);
    }
    menu.hidden = collections.length === 0;
  } catch (error) {
    links.textContent = "Saved movie links are unavailable. Reload after the local API is ready.";
    menu.hidden = false;
    console.warn("Saved movie navigation:", error.message);
  }
})();
