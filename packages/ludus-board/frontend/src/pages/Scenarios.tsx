import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type FixtureRef, type FixtureRoot, type FixtureUsedBy, type Scenario } from "../api";
import DetailModal from "../components/DetailModal";
import EyeIcon from "../components/EyeIcon";
import FixturePreviewModal from "../components/FixturePreviewModal";
import FixtureUploadDialog from "../components/FixtureUploadDialog";
import UploadIcon from "../components/UploadIcon";

interface ParsedExpectation {
  type: string;
  must_have_fields?: string[];
  any_of?: string[];
  rubric?: string;
  pass_threshold?: number;
}

interface ParsedGate {
  min_pass_rate?: number;
  max_regression_vs_baseline?: number;
}

/**
 * Best-effort, line-based extraction of the `expectations:` and `gate:` blocks
 * from the scenario YAML source. Intentionally NOT a general YAML parser (no new
 * dependency per task scope) — only understands the specific shapes emitted by
 * ludus scenario files (ExpectationSchema / Gate in scenario.py). Returns null
 * for a section it cannot confidently parse, so the caller can fall back to
 * rendering only the YAML source.
 */
function parseExpectationsAndGate(yaml: string): { expectations: ParsedExpectation[] | null; gate: ParsedGate | null } {
  const lines = yaml.split(/\r?\n/);

  function topLevelBlock(key: string): string[] | null {
    const startIdx = lines.findIndex((l) => new RegExp(`^${key}:\\s*$`).test(l));
    if (startIdx === -1) return null;
    const block: string[] = [];
    for (let i = startIdx + 1; i < lines.length; i++) {
      const line = lines[i];
      if (line.trim() === "") continue;
      if (/^\S/.test(line)) break; // back to column 0 = new top-level key
      block.push(line);
    }
    return block;
  }

  let expectations: ParsedExpectation[] | null = null;
  const expBlock = topLevelBlock("expectations");
  if (expBlock) {
    try {
      const items: ParsedExpectation[] = [];
      let current: ParsedExpectation | null = null;
      let currentListKey: "must_have_fields" | "any_of" | null = null;
      for (const raw of expBlock) {
        const listItemMatch = raw.match(/^\s*-\s*type:\s*(\S+)\s*$/);
        if (listItemMatch) {
          if (current) items.push(current);
          current = { type: listItemMatch[1] };
          currentListKey = null;
          continue;
        }
        if (!current) continue;
        const scalarMatch = raw.match(/^\s*(rubric|pass_threshold):\s*(.+?)\s*$/);
        if (scalarMatch) {
          currentListKey = null;
          if (scalarMatch[1] === "pass_threshold") current.pass_threshold = Number(scalarMatch[2]);
          else current.rubric = scalarMatch[2].replace(/^["']|["']$/g, "");
          continue;
        }
        const listKeyMatch = raw.match(/^\s*(must_have_fields|any_of):\s*$/);
        if (listKeyMatch) {
          currentListKey = listKeyMatch[1] as "must_have_fields" | "any_of";
          current[currentListKey] = [];
          continue;
        }
        const listValueMatch = raw.match(/^\s*-\s*(.+?)\s*$/);
        if (listValueMatch && currentListKey) {
          current[currentListKey]!.push(listValueMatch[1].replace(/^["']|["']$/g, ""));
          continue;
        }
      }
      if (current) items.push(current);
      if (items.length > 0 && items.every((it) => it.type)) expectations = items;
    } catch {
      expectations = null;
    }
  }

  let gate: ParsedGate | null = null;
  const gateBlock = topLevelBlock("gate");
  if (gateBlock) {
    try {
      const g: ParsedGate = {};
      for (const raw of gateBlock) {
        const m = raw.match(/^\s*(min_pass_rate|max_regression_vs_baseline):\s*([\d.]+)\s*$/);
        if (m) g[m[1] as keyof ParsedGate] = Number(m[2]);
      }
      if (g.min_pass_rate !== undefined || g.max_regression_vs_baseline !== undefined) gate = g;
    } catch {
      gate = null;
    }
  }

  return { expectations, gate };
}

export default function Scenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [error, setError] = useState<string>();
  const [running, setRunning] = useState<string>();
  const navigate = useNavigate();

  const [selectedId, setSelectedId] = useState<string>();
  const [detail, setDetail] = useState<Scenario>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string>();

  // --- Fixtures (story s6886e332): list/preview/upload state for the open scenario ---
  const [fixtures, setFixtures] = useState<FixtureRef[]>();
  const [fixturesError, setFixturesError] = useState<string>();
  const [previewTarget, setPreviewTarget] = useState<{ root: FixtureRoot; path: string }>();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [replaceTarget, setReplaceTarget] = useState<
    { root: FixtureRoot; path: string; usedBy: FixtureUsedBy[] } | undefined
  >(undefined);

  useEffect(() => {
    api.listScenarios().then(setScenarios).catch((e) => setError(String(e)));
  }, []);

  function loadFixtures(scenarioId: string) {
    setFixturesError(undefined);
    api
      .listScenarioFixtures(scenarioId)
      .then(setFixtures)
      .catch((e) => setFixturesError(String(e)));
  }

  function openReplace(ref: FixtureRef) {
    api
      .getFixtureContent(ref.root, ref.path)
      .then((content) =>
        setReplaceTarget({ root: ref.root, path: ref.path, usedBy: content.used_by }),
      )
      .catch(() => setReplaceTarget({ root: ref.root, path: ref.path, usedBy: [] }));
    setUploadOpen(true);
  }

  async function run(s: Scenario) {
    setRunning(s.id);
    setError(undefined);
    try {
      const run = await api.createRun(s.id, s.target);
      navigate(`/runs/${run.id}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(undefined);
    }
  }

  function openDetail(s: Scenario) {
    setSelectedId(s.id);
    setDetail(undefined);
    setDetailError(undefined);
    setDetailLoading(true);
    setFixtures(undefined);
    api
      .getScenario(s.id)
      .then(setDetail)
      .catch((e) => setDetailError(String(e)))
      .finally(() => setDetailLoading(false));
    loadFixtures(s.id);
  }

  function closeDetail() {
    setSelectedId(undefined);
    setFixtures(undefined);
  }

  const parsed = detail?.yaml_source ? parseExpectationsAndGate(detail.yaml_source) : { expectations: null, gate: null };

  return (
    <div>
      <h1>Scenarios</h1>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <table>
          <thead>
            <tr><th>Id</th><th>Target</th><th>Repeat</th><th>Description</th><th className="col-actions"></th></tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{s.target}</td>
                <td>{s.repeat}</td>
                <td className="muted">{s.description}</td>
                <td className="col-actions">
                  <div className="row-actions">
                    <button className="icon-btn" title="View details" onClick={() => openDetail(s)}>
                      <EyeIcon />
                    </button>
                    <button disabled={running === s.id} onClick={() => run(s)}>
                      {running === s.id ? "Running…" : "Run"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <DetailModal
        title="Scenario detail"
        subtitle={selectedId}
        open={selectedId !== undefined}
        loading={detailLoading}
        error={detailError}
        onClose={closeDetail}
        footer={<button className="secondary" onClick={closeDetail}>Close</button>}
      >
        {detail && (
          <>
            <div className="section-title">Overview</div>
            <dl className="kv-grid">
              <dt>Id</dt><dd>{detail.id}</dd>
              <dt>Target</dt><dd>{detail.target}</dd>
              <dt>Repeat</dt><dd>{detail.repeat}</dd>
              <dt>Description</dt><dd>{detail.description}</dd>
            </dl>

            <div className="section-title">Fixtures{fixtures ? ` (${fixtures.length})` : ""}</div>
            {fixturesError && <p className="error">{fixturesError}</p>}
            {!fixturesError && !fixtures && <p className="empty-note">Loading fixtures…</p>}
            {!fixturesError && fixtures && fixtures.length === 0 && (
              <p className="empty-note">This scenario does not reference any fixtures.</p>
            )}
            {!fixturesError && fixtures && fixtures.length > 0 && (
              <ul className="fixture-list">
                {fixtures.map((f, i) => (
                  <li className={`fixture-item${f.present ? "" : " missing"}`} key={i}>
                    <span className="fixture-role">{f.role}</span>
                    <span className="fixture-path">{f.root}/{f.path}</span>
                    <span className="fixture-meta">
                      {f.present
                        ? `${f.size_bytes !== null && f.size_bytes < 1024 ? `${f.size_bytes} B` : f.size_bytes !== null ? `${(f.size_bytes / 1024).toFixed(1)} KB` : "—"}${f.content_type ? ` · ${f.content_type}` : ""}`
                        : "—"}
                    </span>
                    <span className={`badge ${f.present ? "pass" : "fail"}`}>
                      {f.present ? "present" : "missing"}
                    </span>
                    <div className="fixture-actions">
                      {f.present ? (
                        <>
                          <button
                            className="icon-btn"
                            title="Preview"
                            onClick={() => setPreviewTarget({ root: f.root, path: f.path })}
                          >
                            <EyeIcon />
                          </button>
                          <button className="icon-btn" title="Replace" onClick={() => openReplace(f)}>
                            <UploadIcon />
                          </button>
                        </>
                      ) : (
                        <button title="Upload" onClick={() => openReplace(f)}>
                          Upload…
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <div style={{ marginTop: "0.7rem" }}>
              <button
                className="secondary"
                style={{ background: "transparent", color: "var(--text)", border: "1px solid var(--border)" }}
                onClick={() => {
                  setReplaceTarget(undefined);
                  setUploadOpen(true);
                }}
              >
                + Add fixture
              </button>
            </div>

            {parsed.expectations && (
              <>
                <div className="section-title">Expectations</div>
                <ul className="exp-list">
                  {parsed.expectations.map((exp, i) => (
                    <li className="exp-item" key={i}>
                      <span className="exp-type">{exp.type}</span>
                      <span className="exp-detail">
                        {[
                          exp.must_have_fields?.length ? `must_have_fields: ${exp.must_have_fields.join(", ")}` : null,
                          exp.any_of?.length ? `any_of: ${exp.any_of.join(", ")}` : null,
                          exp.rubric ? `rubric: ${exp.rubric}` : null,
                          exp.pass_threshold !== undefined ? `pass_threshold: ${exp.pass_threshold}` : null,
                        ].filter(Boolean).join(" · ")}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {parsed.gate && (
              <>
                <div className="section-title">Gate</div>
                <div className="gate-box">
                  {parsed.gate.min_pass_rate !== undefined && (
                    <div className="g"><span className="label">Min pass rate</span><span className="val">{parsed.gate.min_pass_rate}</span></div>
                  )}
                  {parsed.gate.max_regression_vs_baseline !== undefined && (
                    <div className="g"><span className="label">Max regression vs baseline</span><span className="val">{parsed.gate.max_regression_vs_baseline}</span></div>
                  )}
                </div>
              </>
            )}

            {!parsed.expectations && !parsed.gate && (
              <p className="empty-note">Expectations/Gate could not be parsed structurally — see YAML source below.</p>
            )}

            <div className="section-title">YAML source</div>
            <pre>{detail.yaml_source ?? "(no YAML source available)"}</pre>
          </>
        )}
      </DetailModal>

      <FixturePreviewModal
        open={previewTarget !== undefined}
        root={previewTarget?.root}
        path={previewTarget?.path}
        onClose={() => setPreviewTarget(undefined)}
        onUpload={(root, path) => {
          setPreviewTarget(undefined);
          setReplaceTarget({ root, path, usedBy: [] });
          setUploadOpen(true);
        }}
      />

      <FixtureUploadDialog
        open={uploadOpen}
        scenarioId={selectedId ?? ""}
        replaceTarget={replaceTarget}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => {
          if (selectedId) loadFixtures(selectedId);
        }}
      />
    </div>
  );
}
