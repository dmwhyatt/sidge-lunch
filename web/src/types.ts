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

export interface Vendor extends Place {
  menu_url: string;
}

export interface Faculty extends Place {
  building: string;
}

export interface Walk {
  seconds: number;
  metres: number;
  estimated: boolean; // true when straight-line fallback, not a real route
}

export interface WalkingFile {
  source: string | null;
  generated_at: string | null;
  times: Record<string, Record<string, { seconds: number; metres: number }>>;
}
