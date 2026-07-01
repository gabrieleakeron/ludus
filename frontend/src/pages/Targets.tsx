import { useEffect, useState } from "react";
import { api, type Target } from "../api";

export default function Targets() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [error, setError] = useState<string>();

  useEffect(() => {
    api.listTargets().then(setTargets).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">{error}</p>;

  return (
    <div>
      <h1>Targets</h1>
      <div className="card">
        <table>
          <thead>
            <tr><th>Key</th><th>Kind</th><th>Description</th><th>API key</th></tr>
          </thead>
          <tbody>
            {targets.map((t) => (
              <tr key={t.key}>
                <td>{t.key}</td>
                <td>{t.kind}</td>
                <td className="muted">{t.description}</td>
                <td>{t.requires_api_key ? "required" : "keyless"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
