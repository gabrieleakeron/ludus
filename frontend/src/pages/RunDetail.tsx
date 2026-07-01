import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type RunDetail as RunDetailT } from "../api";

export default function RunDetail() {
  const { id } = useParams();
  const [run, setRun] = useState<RunDetailT>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!id) return;
    api.getRun(Number(id)).then(setRun).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!run) return <p className="muted">Loading…</p>;

  return (
    <div>
      <h1>Run #{run.id} — {run.scenario_id}</h1>
      <div className="card">
        <p>
          Target <b>{run.target}</b> · N={run.n} ·
          overall <b>{run.overall_mean.toFixed(4)}</b> ·
          pass rate <b>{(run.pass_rate * 100).toFixed(0)}%</b> ·
          gate {run.gate_evaluated ? (run.gate_passed ? "PASS" : "FAIL") : "n/a"}
        </p>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr><th>Rep</th><th>Status</th><th>Score</th><th>Cost $</th><th>Latency ms</th><th>Tokens in/out</th></tr>
          </thead>
          <tbody>
            {run.outcomes.map((o) => (
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
      </div>

      {run.report_text && (
        <div className="card">
          <h3>Report</h3>
          <pre>{run.report_text}</pre>
        </div>
      )}
    </div>
  );
}
