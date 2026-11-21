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

export type Person = { key: string; name: string; role: string; language: string };
export type Clinic = { key: string; doctor: string; clinic: string };

export type AppState = {
  dry_run: boolean;
  swiggy: boolean;
  user: string;
  people: Person[];
  clinics: Clinic[];
  cards: CardRow[];
  recent: CardRow[];
  jobs: Job[];
  ringing: Job[];
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
};
