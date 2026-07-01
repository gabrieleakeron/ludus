// Typed client for the Ludus backend REST API.
// Base URL: VITE_API_URL if set (e.g. http://localhost:8000), otherwise "/api"
// which is proxied to the backend (Vite dev proxy or nginx in production).

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "/api";

export interface Target {
  key: string;
  kind: string;
  description: string;
  requires_api_key: boolean;
  runnable: boolean;
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

// --- Fixtures (story s6886e332) — shapes mirror the story's `## API Contract` 1:1 ---

export type FixtureRoot = "fixtures" | "rubrics";
export type FixtureRole = "prompt_fixture" | "context_files" | "rubric";

export interface FixtureRef {
  root: FixtureRoot;
  path: string;
  role: FixtureRole;
  scenario_id: string;
  present: boolean;
  size_bytes: number | null;
  is_binary: boolean | null;
  content_type: string | null;
}

export interface FixtureUsedBy {
  scenario_id: string;
  role: FixtureRole;
}

export interface FixtureContent {
  root: FixtureRoot;
  path: string;
  present: boolean;
  size_bytes: number | null;
  is_binary: boolean;
  truncated: boolean;
  content: string | null;
  content_type: string | null;
  used_by: FixtureUsedBy[];
}

export interface FixtureUploadResult {
  root: FixtureRoot;
  path: string;
  size_bytes: number;
  created: boolean;
}

export interface FixtureConfig {
  roots: FixtureRoot[];
  preview_max_bytes: number;
  upload_max_bytes: number;
  text_extensions: string[];
  upload_extensions: string[];
}

/** Extract a readable message from a JSON `{"detail": "..."}` error body, falling back to raw text. */
function extractDetail(text: string): string {
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // not JSON — fall through to raw text
  }
  return text;
}

/** Error carrying the HTTP status code so callers can branch on 409/413/415/etc. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const detail = extractDetail(await resp.text());
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

export const api = {
  health: () => req<{ status: string; ludus_version: string }>("GET", "/health"),
  listTargets: () => req<Target[]>("GET", "/targets"),
  getTarget: (key: string) => req<Target>("GET", `/targets/${encodeURIComponent(key)}`),
  listScenarios: () => req<Scenario[]>("GET", "/scenarios"),
  getScenario: (id: string) => req<Scenario>("GET", `/scenarios/${id}`),
  listRuns: (scenarioId?: string) =>
    req<RunSummary[]>("GET", `/runs${scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : ""}`),
  getRun: (id: number) => req<RunDetail>("GET", `/runs/${id}`),
  createRun: (scenario_id: string, target?: string, n?: number) =>
    req<RunDetail>("POST", "/runs", { scenario_id, target, n }),

  listScenarioFixtures: (scenarioId: string) =>
    req<FixtureRef[]>("GET", `/scenarios/${encodeURIComponent(scenarioId)}/fixtures`),
  getFixtureContent: (root: FixtureRoot, path: string) =>
    req<FixtureContent>(
      "GET",
      `/fixtures/content?root=${encodeURIComponent(root)}&path=${encodeURIComponent(path)}`,
    ),
  getFixtureConfig: () => req<FixtureConfig>("GET", "/fixtures/config"),
  /**
   * Upload a new fixture, or replace an existing one when `overwrite` is true.
   * Multipart via FormData (not JSON) — the backend's POST /fixtures reads
   * `root`/`path`/`overwrite` as form fields and `file` as the upload part.
   */
  async uploadFixture(
    root: FixtureRoot,
    path: string,
    file: File,
    overwrite: boolean,
  ): Promise<FixtureUploadResult> {
    const form = new FormData();
    form.append("root", root);
    form.append("path", path);
    form.append("overwrite", String(overwrite));
    form.append("file", file);
    const resp = await fetch(`${BASE}/fixtures`, { method: "POST", body: form });
    if (!resp.ok) {
      const detail = extractDetail(await resp.text());
      throw new ApiError(resp.status, detail);
    }
    return (await resp.json()) as FixtureUploadResult;
  },
};
