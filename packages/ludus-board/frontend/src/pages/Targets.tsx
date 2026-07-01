import { useEffect, useState } from "react";
import { api, type Target } from "../api";
import DetailModal from "../components/DetailModal";
import EyeIcon from "../components/EyeIcon";

function apiKeyPill(requiresApiKey: boolean) {
  return requiresApiKey
    ? <span className="api-pill required">required</span>
    : <span className="api-pill keyless">keyless</span>;
}

export default function Targets() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [error, setError] = useState<string>();

  const [selectedKey, setSelectedKey] = useState<string>();
  const [detail, setDetail] = useState<Target>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string>();

  useEffect(() => {
    api.listTargets().then(setTargets).catch((e) => setError(String(e)));
  }, []);

  function openDetail(t: Target) {
    setSelectedKey(t.key);
    setDetail(undefined);
    setDetailError(undefined);
    setDetailLoading(true);
    api
      .getTarget(t.key)
      .then(setDetail)
      .catch((e) => setDetailError(String(e)))
      .finally(() => setDetailLoading(false));
  }

  function closeDetail() {
    setSelectedKey(undefined);
  }

  if (error) return <p className="error">{error}</p>;

  return (
    <div>
      <h1>Targets</h1>
      <div className="card">
        <table>
          <thead>
            <tr><th>Key</th><th>Kind</th><th>Description</th><th>API key</th><th className="col-actions"></th></tr>
          </thead>
          <tbody>
            {targets.map((t) => (
              <tr key={t.key}>
                <td>{t.key}</td>
                <td>{t.kind}</td>
                <td className="muted">{t.description}</td>
                <td>{t.requires_api_key ? "required" : "keyless"}</td>
                <td className="col-actions">
                  <div className="row-actions">
                    <button className="icon-btn" title="View details" onClick={() => openDetail(t)}>
                      <EyeIcon />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <DetailModal
        title="Target detail"
        subtitle={selectedKey}
        open={selectedKey !== undefined}
        loading={detailLoading}
        error={detailError}
        onClose={closeDetail}
        footer={<button className="secondary" onClick={closeDetail}>Close</button>}
      >
        {detail && (
          <>
            <div className="section-title">Overview</div>
            <dl className="kv-grid">
              <dt>Key</dt><dd>{detail.key}</dd>
              <dt>Kind</dt><dd>{detail.kind}</dd>
              <dt>Description</dt><dd>{detail.description}</dd>
              <dt>API key</dt><dd>{apiKeyPill(detail.requires_api_key)}</dd>
              <dt>Runnable</dt>
              <dd>
                {detail.runnable
                  ? <span className="badge pass">runnable</span>
                  : <span className="badge fail">not runnable</span>}
              </dd>
            </dl>

            <div className="section-title">Metadata</div>
            <p className="empty-note">No additional metadata exposed for this target.</p>
          </>
        )}
      </DetailModal>
    </div>
  );
}
