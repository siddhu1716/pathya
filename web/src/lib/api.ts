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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
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
  callForList: (person: string) => post<{ job: string }>(`/api/kitchen/call/${person}`),
  checkin: (person: string, purpose?: string) =>
    post<{ job: string }>(`/api/health/checkin/${person}`, purpose ? { purpose } : {}),
  book: (b: { patient: string; clinic: string; window_start: string; window_end: string; part: string; reason: string }) =>
    post<{ job: string }>("/api/health/book", b),
  prescription: (patient: string, photo: File) => {
    const form = new FormData();
    form.append("patient", patient);
    form.append("photo", photo);
    return request<{ card: string }>("/api/health/rx", { method: "POST", body: form });
  },
  tap: (id: string, choice: string) => post<CardRow>(`/api/cards/${id}/tap`, { choice }),
  reject: (id: string) => post<{ ok: boolean }>(`/api/cards/${id}/reject`),
  runNow: (id: string) => post<{ ok: boolean }>(`/api/jobs/${id}/run-now`),
  icsUrl: (id: string) => `/api/cards/${id}/ics`,
  calls: () => request<CallRecord[]>("/api/calls"),
  orders: () => request<Order[]>("/api/orders"),
  line: (id: string, line: Line) => post<{ ok: boolean }>(`/api/calls/${id}/line`, line),
  kitchen: () => request<KitchenOverview>("/api/kitchen/overview"),
  reorder: (items: string[]) => post<{ card: string }>("/api/kitchen/reorder", { items }),
  mealplan: (days: number, notes: string) => post<{ card: string; plan: MealPlan }>("/api/kitchen/mealplan", { days, notes }),
  nutrition: () => post<Nutrition>("/api/kitchen/nutrition"),
  shareNutrition: () => post<{ card: string }>("/api/kitchen/nutrition/share"),
};

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
