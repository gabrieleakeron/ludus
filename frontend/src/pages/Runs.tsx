import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type RunSummary } from "../api";

function gateBadge(r: RunSummary) {
  if (!r.gate_evaluated) return <span className="badge">no gate</span>;
  return r.gate_passed
    ? <span className="badge pass">PASS</span>
    : <span className="badge fail">FAIL</span>;
}

export default function Runs() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string>();

  useEffect(() => {
    api.listRuns().then(setRuns).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">{error}</p>;

  return (
    <div>
      <h1>Runs</h1>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Scenario</th><th>Target</th><th>N</th>
              <th>Overall</th><th>Pass rate</th><th>Gate</th><th>When</th>
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
                <td>{gateBadge(r)}</td>
                <td className="muted">{r.created_at?.replace("T", " ").slice(0, 19)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.length === 0 && <p className="muted">No runs yet — trigger one from Scenarios.</p>}
      </div>
    </div>
  );
}
