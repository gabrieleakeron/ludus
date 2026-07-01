import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type RunDetail as RunDetailT, type RunSummary } from "../api";
import DetailModal from "../components/DetailModal";
import EyeIcon from "../components/EyeIcon";

function gateBadge(gateEvaluated: boolean, gatePassed: boolean | null) {
  if (!gateEvaluated) return <span className="badge">no gate</span>;
  return gatePassed
    ? <span className="badge pass">PASS</span>
    : <span className="badge fail">FAIL</span>;
}

export default function Runs() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string>();

  const [selectedId, setSelectedId] = useState<number>();
  const [detail, setDetail] = useState<RunDetailT>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string>();

  useEffect(() => {
    api.listRuns().then(setRuns).catch((e) => setError(String(e)));
  }, []);

  function openDetail(r: RunSummary) {
    setSelectedId(r.id);
    setDetail(undefined);
    setDetailError(undefined);
    setDetailLoading(true);
    api
      .getRun(r.id)
      .then(setDetail)
      .catch((e) => setDetailError(String(e)))
      .finally(() => setDetailLoading(false));
  }

  function closeDetail() {
    setSelectedId(undefined);
  }

  if (error) return <p className="error">{error}</p>;

  return (
    <div>
      <h1>Runs</h1>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Scenario</th><th>Target</th><th>N</th>
              <th>Overall</th><th>Pass rate</th><th>Gate</th><th>When</th><th className="col-actions"></th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td><Link to={`/runs/${r.id}`}>{r.id}</Link></td>
                <td>{r.scenario_id}</td>
                <td>{r.target}</td>
                <td>{r.n}</td>
                <td>{r.overall_mean.toFixed(4)}</td>
                <td>{(r.pass_rate * 100).toFixed(0)}%</td>
                <td>{gateBadge(r.gate_evaluated, r.gate_passed)}</td>
                <td className="muted">{r.created_at?.replace("T", " ").slice(0, 19)}</td>
                <td className="col-actions">
                  <div className="row-actions">
                    <button className="icon-btn" title="View details" onClick={() => openDetail(r)}>
                      <EyeIcon />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.length === 0 && <p className="muted">No runs yet — trigger one from Scenarios.</p>}
      </div>

      <DetailModal
        title="Run detail"
        subtitle={detail ? `#${detail.id} — ${detail.scenario_id}` : selectedId !== undefined ? `#${selectedId}` : undefined}
        open={selectedId !== undefined}
        loading={detailLoading}
        error={detailError}
        onClose={closeDetail}
        footer={
          <>
            {selectedId !== undefined ? (
              <span className="footer-link">Open full page: <Link to={`/runs/${selectedId}`} onClick={closeDetail}>/runs/{selectedId}</Link></span>
            ) : <span />}
            <button className="secondary" onClick={closeDetail}>Close</button>
          </>
        }
      >
        {detail && (
          <>
            <div className="section-title">Aggregated outcome</div>
            <div className="summary-row">
              <div className="g"><span className="label">Target</span><span className="val">{detail.target}</span></div>
              <div className="g"><span className="label">N</span><span className="val">{detail.n}</span></div>
              <div className="g"><span className="label">Overall mean</span><span className="val">{detail.overall_mean.toFixed(4)}</span></div>
              <div className="g"><span className="label">Pass rate</span><span className="val">{(detail.pass_rate * 100).toFixed(0)}%</span></div>
              <div className="g"><span className="label">Gate</span><span className="val">{gateBadge(detail.gate_evaluated, detail.gate_passed)}</span></div>
            </div>

            <div className="section-title">Outcomes per repetition</div>
            <table>
              <thead>
                <tr><th>Rep</th><th>Status</th><th>Score</th><th>Cost $</th><th>Latency ms</th><th>Tokens in/out</th></tr>
              </thead>
              <tbody>
                {detail.outcomes.map((o) => (
                  <tr key={o.idx}>
                    <td>{o.idx + 1}</td>
                    <td>{o.status}</td>
                    <td>{o.score.toFixed(4)}</td>
                    <td>{o.cost_usd.toFixed(6)}</td>
                    <td>{o.latency_ms.toFixed(0)}</td>
                    <td>{o.tokens_input} / {o.tokens_output}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {detail.report_text && (
              <>
                <div className="section-title">Report</div>
                <pre>{detail.report_text}</pre>
              </>
            )}
          </>
        )}
      </DetailModal>
    </div>
  );
}
