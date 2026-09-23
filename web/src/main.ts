import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./style.css";
import {
  DEFAULT_FILTERS,
  cheapest,
  filterMeals,
  formatWalk,
  londonToday,
  timeAgo,
  todaysDay,
  walkFor,
  type Filters,
} from "./logic";
import { ALLERGENS, type Allergen } from "./types";
import type { Dietary, Faculty, Meal, Vendor, VendorMenu, Walk, WalkingFile } from "./types";

const DIETARY_ABBR: Record<Dietary, string> = {
  vegan: "VG",
  vegetarian: "V",
  "gluten-free": "GF",
  "dairy-free": "DF",
  halal: "H",
};
const FACULTY_KEY = "sidge-lunch:faculty";

interface Data {
  vendors: Vendor[];
  faculties: Faculty[];
  menus: Record<string, VendorMenu>;
  walking: WalkingFile;
}

interface Row {
  vendor: Vendor;
  menu: VendorMenu | undefined;
  walk: Walk;
  meals: Meal[];
  hasToday: boolean;
}

const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T;

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

async function getJson<T>(name: string): Promise<T> {
  const r = await fetch(`${import.meta.env.BASE_URL}${name}`, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

async function load(): Promise<Data> {
  const [v, f, m, walking] = await Promise.all([
    getJson<{ vendors: Vendor[] }>("vendors.json"),
    getJson<{ faculties: Faculty[] }>("faculties.json"),
    getJson<{ vendors: Record<string, VendorMenu> }>("menus.json"),
    getJson<WalkingFile>("walking.json").catch(() => ({ source: null, generated_at: null, times: {} })),
  ]);
  return { vendors: v.vendors, faculties: f.faculties, menus: m.vendors, walking };
}

function storedFaculty(faculties: Faculty[]): Faculty {
  try {
    const id = localStorage.getItem(FACULTY_KEY);
    const found = faculties.find((f) => f.id === id);
    if (found) return found;
  } catch {
    // storage unavailable; fall through to default
  }
  return faculties[0];
}

function readFilters(): Filters & { sort: "walk" | "price" } {
  const form = $<HTMLFormElement>("#filters");
  const dietary = [...form.querySelectorAll<HTMLInputElement>('input[name="dietary"]:checked')].map(
    (i) => i.value as Dietary,
  );
  const excludeAllergens = [...form.querySelectorAll<HTMLInputElement>('input[name="allergen"]:checked')].map(
    (i) => i.value as Allergen,
  );
  const range = $<HTMLInputElement>("#max-price");
  const max = Number(range.value);
  return {
    ...DEFAULT_FILTERS,
    dietary,
    excludeAllergens,
    maxPrice: max >= Number(range.max) ? null : max,
    includeUnpriced: $<HTMLInputElement>("#include-unpriced").checked,
    lunchOnly: $<HTMLInputElement>("#lunch-only").checked,
    sort: $<HTMLSelectElement>("#sort").value as "walk" | "price",
  };
}

function statusLine(row: Row): string {
  if (row.vendor.link_only) {
    return `<p class="status">Menu is on the vendor's own website.</p>`;
  }
  const m = row.menu;
  if (!m || m.status === "unsupported") {
    return `<p class="status">Menu not collected yet. See the vendor's own page.</p>`;
  }
  const updated = m.updated_at ? `updated ${timeAgo(m.updated_at)}` : "never collected";
  if (m.status === "error") {
    return `<p class="status error">Couldn't read the latest menu (last ${updated}). Check the vendor's page.</p>`;
  }
  if (!row.hasToday) return `<p class="status">No menu published for today (${updated}).</p>`;
  return `<p class="status">Menu ${updated}.</p>`;
}

function mealsHtml(row: Row): string {
  if (!row.hasToday) return "";
  if (row.meals.length === 0) return `<p class="empty">Nothing matches your filters.</p>`;
  return row.meals
    .map(
      (meal) => `
      <div class="meal">
        <h3>${esc(meal.name)}${meal.service ? ` <span>${esc(meal.service)}</span>` : ""}</h3>
        <ul class="items">
          ${meal.items
            .map((item) => {
              const chips = item.dietary
                .filter((t) => !(t === "vegetarian" && item.dietary.includes("vegan")))
                .map((t) => `<abbr class="chip" title="${t}">${DIETARY_ABBR[t]}</abbr>`)
                .join("");
              const price = item.price_text
                ? `<span class="item-price">${esc(item.price_text)}</span>`
                : `<span class="item-price unlisted">price not listed</span>`;
              return `<li>
                <span class="item-name">${esc(item.name)}${chips ? `<span class="chips">${chips}</span>` : ""}</span>
                ${price}
                ${item.description ? `<span class="item-desc">${esc(item.description)}</span>` : ""}
                ${item.allergens.length ? `<span class="item-allergens">Contains: ${item.allergens.join(", ")}</span>` : ""}
              </li>`;
            })
            .join("")}
        </ul>
        ${meal.note ? `<p class="meal-note">${esc(meal.note)}</p>` : ""}
      </div>`,
    )
    .join("");
}

function sourceLink(row: Row): string {
  return `<a class="source" href="${esc(row.vendor.menu_url)}" target="_blank" rel="noopener">Vendor's menu page ↗</a>`;
}

function main(data: Data) {
  const today = londonToday();
  $("#today").textContent = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  if (data.walking.source) {
    $("#walk-source").textContent = `Walking times: ${data.walking.source}. Times marked ≈ are straight-line estimates.`;
  } else {
    $("#walk-source").textContent = "Walking times marked ≈ are straight-line estimates.";
  }

  $("#allergen-options").innerHTML = ALLERGENS.map(
    (a) => `<label><input type="checkbox" name="allergen" value="${a}" /> ${a}</label>`,
  ).join("");

  const select = $<HTMLSelectElement>("#faculty");
  select.innerHTML = data.faculties
    .map((f) => `<option value="${esc(f.id)}">${esc(f.name)}</option>`)
    .join("");
  let faculty = storedFaculty(data.faculties);
  select.value = faculty.id;
  let selectedVendor: string | null = null;

  // Map
  const map = L.map("map", { scrollWheelZoom: true });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  map.fitBounds(L.latLngBounds([...data.vendors, ...data.faculties].map((p) => [p.lat, p.lng])), {
    padding: [70, 30], // pin labels are centred on the point, so leave room either side
  });

  const pinIcon = (label: string, cls: string) =>
    L.divIcon({ className: "pin-host", html: `<span class="pin ${cls}">${esc(label)}</span>`, iconSize: [0, 0] });

  const facultyMarker = L.marker([faculty.lat, faculty.lng], {
    icon: pinIcon("You", "faculty"),
    keyboard: false,
    zIndexOffset: -100,
  }).addTo(map);

  const vendorMarkers = new Map<string, L.Marker>();
  for (const v of data.vendors) {
    const m = L.marker([v.lat, v.lng], { icon: pinIcon(v.name, ""), title: v.name }).addTo(map);
    m.bindPopup("", { maxWidth: 320, autoPanPadding: [20, 20] });
    m.on("popupopen", () => select_(v.id, false));
    vendorMarkers.set(v.id, m);
  }

  let rows: Row[] = [];

  function select_(id: string, openPopup: boolean) {
    selectedVendor = id;
    document.querySelectorAll(".vendor").forEach((el) => el.classList.toggle("selected", el.id === `v-${id}`));
    for (const [vid, marker] of vendorMarkers) {
      marker.getElement()?.querySelector(".pin")?.classList.toggle("selected", vid === id);
    }
    // Side by side, keep the card list in step with the map. Stacked (phones), the map
    // sits above the list, so bring the map into view instead of scrolling away from it.
    const sideBySide = window.matchMedia("(min-width: 801px)").matches;
    if (openPopup) {
      const marker = vendorMarkers.get(id)!;
      marker.openPopup();
      map.panTo(marker.getLatLng());
      if (!sideBySide) $("#map").scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (sideBySide) {
      document.getElementById(`v-${id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function render() {
    const f = readFilters();
    const out = $<HTMLOutputElement>("#max-price-out");
    out.textContent = f.maxPrice === null ? "any" : `£${f.maxPrice.toFixed(2)}`;
    $("#allergen-count").textContent = f.excludeAllergens.length ? `(${f.excludeAllergens.length})` : "";

    rows = data.vendors.map((vendor) => {
      const menu = data.menus[vendor.id];
      const day = todaysDay(menu, today);
      return { vendor, menu, walk: walkFor(data.walking, faculty, vendor), meals: filterMeals(day, f), hasToday: !!day };
    });
    rows.sort((a, b) => {
      // Vendors with matching items today first, then by chosen key.
      const am = a.meals.length > 0 ? 0 : 1;
      const bm = b.meals.length > 0 ? 0 : 1;
      if (am !== bm) return am - bm;
      if (f.sort === "price") {
        const ap = cheapest(a.meals) ?? Infinity;
        const bp = cheapest(b.meals) ?? Infinity;
        if (ap !== bp) return ap - bp;
      }
      return a.walk.seconds - b.walk.seconds;
    });

    $("#vendors").innerHTML = rows
      .map(
        (row) => `
        <article class="vendor${row.vendor.id === selectedVendor ? " selected" : ""}" id="v-${esc(row.vendor.id)}">
          <header>
            <h2><button type="button" data-vendor="${esc(row.vendor.id)}">${esc(row.vendor.name)}</button></h2>
            <span class="walk">${formatWalk(row.walk)}</span>
          </header>
          ${statusLine(row)}
          ${mealsHtml(row)}
          ${sourceLink(row)}
        </article>`,
      )
      .join("");

    for (const row of rows) {
      const marker = vendorMarkers.get(row.vendor.id)!;
      const el = marker.getElement()?.querySelector(".pin");
      el?.classList.toggle("dim", row.meals.length === 0);
      el?.classList.toggle("selected", row.vendor.id === selectedVendor);
      marker.setPopupContent(`
        <div class="vendor-popup">
          <h2>${esc(row.vendor.name)}</h2>
          <div class="walk">${formatWalk(row.walk)} from ${esc(faculty.building)}</div>
          ${statusLine(row)}
          ${mealsHtml(row)}
          ${sourceLink(row)}
        </div>`);
    }
  }

  select.addEventListener("change", () => {
    faculty = data.faculties.find((f) => f.id === select.value)!;
    try {
      localStorage.setItem(FACULTY_KEY, faculty.id);
    } catch {
      // storage unavailable; the choice just won't persist
    }
    facultyMarker.setLatLng([faculty.lat, faculty.lng]);
    render();
  });
  $("#filters").addEventListener("input", render);
  $("#vendors").addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLButtonElement>("button[data-vendor]");
    if (btn) select_(btn.dataset.vendor!, true);
  });

  render();
}

load().then(main, (err) => {
  $("#vendors").innerHTML = `<p class="status error">Couldn't load menu data: ${esc(String(err))}</p>`;
});
