// Mirrors scraper/sidge_lunch/schema.py and the files in data/.

export type Dietary = "vegan" | "vegetarian" | "gluten-free" | "dairy-free" | "halal";

// The 14 UK-declarable allergens. An empty list means "none listed", not "none present".
export const ALLERGENS = [
  "celery", "gluten", "crustaceans", "eggs", "fish", "lupin", "milk",
  "molluscs", "mustard", "nuts", "peanuts", "sesame", "soya", "sulphites",
] as const;
export type Allergen = (typeof ALLERGENS)[number];

export interface Price {
  amount: number;
  currency: string;
}

export interface MenuItem {
  name: string;
  description: string | null;
  category: string | null;
  price: Price | null;
  price_text: string | null;
  dietary: Dietary[];
  allergens: Allergen[];
}

export interface Meal {
  name: string;
  service: string | null;
  note: string | null;
  items: MenuItem[];
}

export interface Day {
  date: string; // YYYY-MM-DD, Europe/London
  meals: Meal[];
}

export type Status = "ok" | "error" | "unsupported";

export interface VendorMenu {
  source_url: string;
  status: Status;
  error: string | null;
  updated_at: string | null;
  content_hash: string | null;
  days: Day[];
}

export interface Place {
  id: string;
  name: string;
  lat: number;
  lng: number;
}

// Order is fixed: it sets each type's colour slot (see style.css) and the legend order.
export const VENDOR_TYPES = ["college", "university", "commercial"] as const;
export type VendorType = (typeof VENDOR_TYPES)[number];
export const VENDOR_TYPE_LABELS: Record<VendorType, string> = {
  college: "College",
  university: "University",
  commercial: "Commercial",
};

export interface Vendor extends Place {
  type: VendorType;
  about?: string; // what it is / sells, e.g. "Pub" or "Sandwiches, wraps and coffee"
  menu_url?: string; // vendor's own page; absent if it has none
  link_only?: boolean; // menu isn't scraped; the site just links to it
  menu?: "regular"; // a standing menu (e.g. a pub's), not one published daily
  hours?: string; // OpenStreetMap opening_hours syntax, shown as written
  notice?: string; // temporary notice, e.g. a closure
  notice_until?: string; // YYYY-MM-DD; the notice is hidden from this date
  approx?: boolean; // position isn't exact
}

export interface Building extends Place {
  occupants?: string; // who is in it, where the name doesn't say
}

export interface Site {
  id: string;
  name: string;
  kind: "university" | "college";
  buildings: Building[];
}

// data/walking/<site>.json: routed walks from each building to nearby places.
export interface SiteWalking {
  source: string | null;
  generated_at: string | null;
  times: Record<string, Record<string, [seconds: number, metres: number]>>;
}

export interface Walk {
  seconds: number;
  metres: number;
  estimated: boolean; // true when straight-line fallback, not a real route
}
