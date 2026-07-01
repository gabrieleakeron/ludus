// Typed client for the Ludus backend REST API.
// Base URL: VITE_API_URL if set (e.g. http://localhost:8000), otherwise "/api"
// which is proxied to the backend (Vite dev proxy or nginx in production).

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "/api";

export interface Target {
  key: string;
  kind: string;
  description: string;
  requires_api_key: boolean;
}

export interface Scenario {
  id: string;
  target: string;
  description: string;
  repeat: number;
  source_path?: string | null;
  yaml_source?: string | null;
}

export interface RunSummary {
  id: number;
  scenario_id: string;
  target: string;
  n: number;
  status: string;
  overall_mean: number;
  pass_rate: number;
  gate_evaluated: boolean;
  gate_passed: boolean | null;
  created_at?: string | null;
}

export interface RunOutcome {
  idx: number;
  status: string;
  score: number;
  cost_usd: number;
  latency_ms: number;
  tokens_input: number;
  tokens_output: number;
  result_json: Record<string, unknown>;
  evaluations_json: Array<Record<string, unknown>>;
}

export interface RunDetail extends RunSummary {
  report_text?: string | null;
  outcomes: RunOutcome[];
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${detail}`);
  }
  return (await resp.json()) as T;
}

export const api = {
  health: () => req<{ status: string; ludus_version: string }>("GET", "/health"),
  listTargets: () => req<Target[]>("GET", "/targets"),
  listScenarios: () => req<Scenario[]>("GET", "/scenarios"),
  getScenario: (id: string) => req<Scenario>("GET", `/scenarios/${id}`),
  listRuns: (scenarioId?: string) =>
    req<RunSummary[]>("GET", `/runs${scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : ""}`),
  getRun: (id: number) => req<RunDetail>("GET", `/runs/${id}`),
  createRun: (scenario_id: string, target?: string, n?: number) =>
    req<RunDetail>("POST", "/runs", { scenario_id, target, n }),
};
