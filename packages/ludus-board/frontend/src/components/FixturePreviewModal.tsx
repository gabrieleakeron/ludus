import { useEffect, useState } from "react";
import { api, type FixtureContent, type FixtureRoot } from "../api";
import DetailModal from "./DetailModal";

export interface FixturePreviewModalProps {
  open: boolean;
  root: FixtureRoot | undefined;
  path: string | undefined;
  onClose: () => void;
  /** Open the upload/replace dialog pre-filled for this fixture (used from the "missing" state's CTA). */
  onUpload: (root: FixtureRoot, path: string) => void;
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const ROLE_LABEL: Record<string, string> = {
  prompt_fixture: "prompt_fixture",
  context_files: "context.files",
  rubric: "expectations.llm_judge.rubric",
};

/**
 * Fixture content preview (mockup mk91bf5b4c): reuses DetailModal chrome in
 * its `modal-wide` variant. Renders one of four states — normal text, empty,
 * missing (referenced but absent, AC3/AC8), or binary/too-large (AC2/AC8) —
 * driven entirely by the shape of the FixtureContent response, no separate
 * client-side state machine needed.
 */
export default function FixturePreviewModal({
  open,
  root,
  path,
  onClose,
  onUpload,
}: FixturePreviewModalProps) {
  const [content, setContent] = useState<FixtureContent>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!open || !root || !path) return;
    setContent(undefined);
    setError(undefined);
    setLoading(true);
    api
      .getFixtureContent(root, path)
      .then(setContent)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [open, root, path]);

  const footer =
    content && !content.present ? (
      <>
        <span className="footer-link">No content to preview.</span>
        <div className="row-actions">
          <button className="secondary" onClick={onClose}>Close</button>
          <button onClick={() => root && path && onUpload(root, path)}>Upload…</button>
        </div>
      </>
    ) : (
      <>
        <span className="footer-link">
          {content?.present
            ? "Read-only preview. Use “Replace” from the fixtures list to upload new content."
            : ""}
        </span>
        <button className="secondary" onClick={onClose}>Close</button>
      </>
    );

  return (
    <DetailModal
      title="Fixture preview"
      subtitle={path ? `${root}/${path}` : undefined}
      open={open}
      loading={loading}
      error={error}
      onClose={onClose}
      footer={footer}
    >
      {content && (
        <>
          <div className="section-title">Overview</div>
          <dl className="kv-grid">
            <dt>Path</dt>
            <dd className="fixture-path">{content.root}/{content.path}</dd>
            {content.used_by.length > 0 && (
              <>
                <dt>Used by</dt>
                <dd>
                  <ul className="scenario-link-list">
                    {content.used_by.map((u, i) => (
                      <li key={i}>
                        {u.scenario_id} · {ROLE_LABEL[u.role] ?? u.role}
                      </li>
                    ))}
                  </ul>
                </dd>
              </>
            )}
            {content.present && (
              <>
                <dt>Size</dt>
                <dd>{formatSize(content.size_bytes)}</dd>
                <dt>Type</dt>
                <dd>{content.content_type ?? (content.is_binary ? "binary" : "text")}</dd>
              </>
            )}
            {!content.present && (
              <>
                <dt>Status</dt>
                <dd><span className="badge fail">missing</span></dd>
              </>
            )}
          </dl>

          {content.present && (
            <>
              <div className="section-title">Content</div>
              {content.is_binary || content.truncated ? (
                <div className="alert alert-warn">
                  <span>&#9432;</span>
                  <span>
                    {content.is_binary
                      ? "Binary file — content preview is not available."
                      : "File is too large to preview inline."}
                  </span>
                </div>
              ) : content.content === "" ? (
                <p className="empty-note">This fixture file exists but is empty (0 bytes).</p>
              ) : (
                <>
                  <div className="preview-toolbar">
                    <span className="muted">Showing full content ({formatSize(content.size_bytes)})</span>
                  </div>
                  <pre>{content.content}</pre>
                </>
              )}
            </>
          )}

          {!content.present && (
            <div className="alert alert-error">
              <span>&#9888;</span>
              <span>
                This fixture is referenced by {content.used_by.length} scenario
                {content.used_by.length === 1 ? "" : "s"} but does not exist on disk. Runs relying
                on it will fail. Upload it now to fix{" "}
                {content.used_by.length === 1 ? "that scenario" : "those scenarios"}.
              </span>
            </div>
          )}
        </>
      )}
    </DetailModal>
  );
}
