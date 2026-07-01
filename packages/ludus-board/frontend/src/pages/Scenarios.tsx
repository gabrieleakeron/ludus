import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Scenario } from "../api";

export default function Scenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [error, setError] = useState<string>();
  const [running, setRunning] = useState<string>();
  const navigate = useNavigate();

  useEffect(() => {
    api.listScenarios().then(setScenarios).catch((e) => setError(String(e)));
  }, []);

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

  return (
    <div>
      <h1>Scenarios</h1>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <table>
          <thead>
            <tr><th>Id</th><th>Target</th><th>Repeat</th><th>Description</th><th></th></tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{s.target}</td>
                <td>{s.repeat}</td>
                <td className="muted">{s.description}</td>
                <td>
                  <button disabled={running === s.id} onClick={() => run(s)}>
                    {running === s.id ? "Running…" : "Run"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
