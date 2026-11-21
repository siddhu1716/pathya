// Typed client for the QuickPick FastAPI backend (app/main.py). The Vite dev server proxies /api to :8000.

export type Choice = { id: string; label: string };

export type CardData = {
  expert: string;
  kind: string; // order | booking | hold | brief | meds | alert | info | followup
  title: string;
  lines: string[];
  total: string | null;
  address: string | null;
  question: string;
  choices: Choice[];
  warnings: string[];
  payload: Record<string, any>;
};

export type CardResult = {
  ok?: boolean;
  dry_run?: boolean;
  message?: string;
  cancel?: string;
  eta?: Record<string, string>;
  pay_url?: string;
  paid?: boolean;
  error?: string;
  jobs?: string[];
  open?: string;
  ics?: string;
};

export type CardRow = {
  id: string;
  expert: string;
  card: CardData;
  status: "waiting" | "running" | "done" | "failed" | "rejected";
  choice: string | null;
  result: CardResult | null;
  created: number;
  updated: number;
};

export type Job = {
  id: string;
  expert: string;
  kind: string;
  person: string;
  payload: Record<string, any>;
  run_at: number;
  status: string;
  result: Record<string, any> | null;
};

export type TimelineEvent = { ts: number; expert: string; ref: string; what: string };

export type Line = { role: "ai" | "them" | "tool"; text: string };

export type LiveCall = {
  id: string;
  who: string;
  kind: string;
  expert: string;
  direction: "inbound" | "outbound";
  started: number;
  lines: Line[];
};

export type Journey = {
  call_started?: number;
  call_ended?: number;
  card_ready?: number;
  tapped?: number;
  placed: number;
  delivered?: number | null;
};

export type Order = {
  id: string;
  store: string; // swiggy | zepto | dry run
  card: string | null;
  ref: string | null;
  items: string[];
  total: string | null;
  address: string | null;
  status: string | null;
  eta: string | null;
  placed: number;
  updated: number;
  delivered: number | null;
  journey: Journey;
};

export type CallRecord = {
  id: string;
  who: string;
  kind: string | null;
  expert: string | null;
  direction: string;
  source: string;
  ended: number;
  seconds: number | null;
  transcript: Line[];
  saved: Record<string, any>;
};

export type Person = { key: string; name: string; role: string; language: string };
export type Clinic = { key: string; doctor: string; clinic: string };

export type AppState = {
  dry_run: boolean;
  swiggy: boolean;
  zepto: boolean;
  phone: boolean;
  phone_number: string | null;
  exotel: boolean;
  user: string;
  language: string;
  daily_call: number | null;
  people: Person[];
  clinics: Clinic[];
  cards: CardRow[];
  recent: CardRow[];
  jobs: Job[];
  ringing: Job[];
  live: LiveCall[];
  orders: Order[];
  timeline: TimelineEvent[];
};

// Where the API lives: the same origin by default (the FastAPI server serves this UI), or another server when the UI is
// hosted elsewhere (Vercel). ?server=https://xyz.trycloudflare.com&key=... on any link is remembered on this device.
const boot = new URLSearchParams(window.location.search);
for (const [param, store] of [["server", "qp_server"], ["key", "qp_key"]] as const) {
  const v = boot.get(param);
  if (v) localStorage.setItem(store, v);
}
if (boot.has("key") || boot.has("server")) {
  boot.delete("key");
  boot.delete("server");
  const qs = boot.toString();
  window.history.replaceState(null, "", window.location.pathname + (qs ? `?${qs}` : ""));
}

export const server = () => (localStorage.getItem("qp_server") || import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");
export const key = () => localStorage.getItem("qp_key") || "";
export const connect = (srv: string, k: string) => {
  srv.trim() ? localStorage.setItem("qp_server", srv.trim()) : localStorage.removeItem("qp_server");
  k.trim() ? localStorage.setItem("qp_key", k.trim()) : localStorage.removeItem("qp_key");
};

/** Where calls ring when real phone calls are on: "phone" (default) or "browser" (this device, live transcript). */
export const ringIn = () => (localStorage.getItem("qp_ring") === "browser" ? "browser" : "phone");
export const setRingIn = (v: "phone" | "browser") => localStorage.setItem("qp_ring", v);
const via = () => (ringIn() === "browser" ? "?via=browser" : "");

/** fetch() against the QuickPick server, with the key. */
export const apiFetch = (path: string, init: RequestInit = {}) =>
  fetch(server() + path, { ...init, headers: { ...(init.headers || {}), ...(key() ? { "X-QuickPick-Key": key() } : {}) } });

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return body as T;
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

export const api = {
  state: () => request<AppState>("/api/state"),
  ask: (text: string) => post<{ reply: string }>("/api/ask", { text }),
  planCart: (text: string) => post<{ card: string }>("/api/kitchen/plan", { text }),
  callForList: (person: string) => post<{ job: string }>(`/api/kitchen/call/${person}${via()}`),
  checkin: (person: string, purpose?: string) =>
    post<{ job: string }>(`/api/health/checkin/${person}${via()}`, purpose ? { purpose } : {}),
  book: (b: { patient: string; clinic: string; window_start: string; window_end: string; part: string; reason: string }) =>
    post<{ job: string }>(`/api/health/book${via()}`, b),
  prescription: (patient: string, photo: File) => {
    const form = new FormData();
    form.append("patient", patient);
    form.append("photo", photo);
    return request<{ card: string }>("/api/health/rx", { method: "POST", body: form });
  },
  tap: (id: string, choice: string) => post<CardRow>(`/api/cards/${id}/tap`, { choice }),
  reject: (id: string) => post<{ ok: boolean }>(`/api/cards/${id}/reject`),
  runNow: (id: string) => post<{ ok: boolean }>(`/api/jobs/${id}/run-now`),
  icsUrl: (id: string) => `${server()}/api/cards/${id}/ics${key() ? `?key=${encodeURIComponent(key())}` : ""}`,
  calls: () => request<CallRecord[]>("/api/calls"),
  orders: () => request<Order[]>("/api/orders"),
  line: (id: string, line: Line) => post<{ ok: boolean }>(`/api/calls/${id}/line`, line),
  kitchen: () => request<KitchenOverview>("/api/kitchen/overview"),
  reorder: (items: string[]) => post<{ card: string }>("/api/kitchen/reorder", { items }),
  mealplan: (days: number, notes: string) => post<{ card: string; plan: MealPlan }>("/api/kitchen/mealplan", { days, notes }),
  nutrition: () => post<Nutrition>("/api/kitchen/nutrition"),
  shareNutrition: () => post<{ card: string }>("/api/kitchen/nutrition/share"),
  usedUp: (k: string) => post<{ ok: boolean }>("/api/kitchen/pantry/used", { key: k }),
  logMeal: (text: string, meal = "") => post<MealEntry>("/api/kitchen/meal", { text, meal }),
  delivered: (id: string) => post<Order>(`/api/orders/${id}/delivered`),
  callMe: () => post<{ job: string }>(`/api/home/call${via()}`),
  daily: (hour: number | null) => post<{ ok: boolean; hour: number | null }>("/api/home/daily", { hour }),
};

export type ShelfItem = {
  key: string; name: string; qty: number; added: number; days: number; store: string;
  left: number; days_left: number; low: boolean;
};
export type MealEntry = Macros & { text: string; meal: string; ts: number };
export type Today = { meals: MealEntry[]; total: Macros; targets: Macros & { source: string } };

export type Usual = { name: string; count: number; typical: number; days_ago: number; store: string; price?: number };
export type MealPlan = {
  days: { day: string; meals: { slot: string; dish: string }[]; kcal: number; protein_g: number; carbs_g: number; fat_g: number; fibre_g: number }[];
  ingredients: { item: string; quantity: string; have_it: boolean }[];
  notes: string;
  made?: number;
  for_days?: number;
};
export type Macros = { kcal: number; protein_g: number; carbs_g: number; fat_g: number; fibre_g: number };
export type Nutrition = {
  days: number; people: number; orders: number; dry_runs: number; per_person_day: Macros;
  split: { protein: number; carbs: number; fat: number }; targets: Macros & { source: string }; made?: number;
};
export type KitchenOverview = {
  usuals: Usual[]; plan: MealPlan | null; nutrition: Nutrition | null; targets: Macros & { source: string };
  pantry: ShelfItem[]; today: Today;
  nutritionist: string | null; cook: string | null; prefs: { people: number; diet: string; cuisine: string };
};

export const ago = (ts: number) => {
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return new Date(ts * 1000).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
};

export const clock = (ts: number) =>
  new Date(ts * 1000).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const span = (a?: number | null, b?: number | null) => {
  if (!a || !b) return "";
  const s = Math.max(0, Math.round(b - a));
  return s < 90 ? `${s}s` : `${Math.round(s / 60)} min`;
};
