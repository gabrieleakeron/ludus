import { useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import { ApiError, api, type FixtureConfig, type FixtureRole, type FixtureRoot, type FixtureUsedBy } from "../api";
import DetailModal from "./DetailModal";

export interface FixtureUploadDialogProps {
  open: boolean;
  /** The scenario whose fixtures section triggered this dialog (shown in the title). */
  scenarioId: string;
  /**
   * When set, the dialog opens in "Replace" mode for this exact (root, path):
   * path is locked read-only and existing `usedBy` scenarios are surfaced as a warning.
   * When undefined, the dialog is in "Add fixture" mode with an editable role/path form.
   */
  replaceTarget?: { root: FixtureRoot; path: string; usedBy: FixtureUsedBy[] };
  onClose: () => void;
  /** Called after a successful upload so the caller can refresh the fixtures list (AC4). */
  onUploaded: () => void;
}

const ROLE_OPTIONS: { value: FixtureRole; label: string }[] = [
  { value: "context_files", label: "context.files" },
  { value: "prompt_fixture", label: "prompt_fixture" },
  { value: "rubric", label: "rubric" },
];

function roleRoot(role: FixtureRole): FixtureRoot {
  return role === "rubric" ? "rubrics" : "fixtures";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Upload / replace fixture dialog (mockup mk30a8f0b5). One component covers
 * both flows since the backend contract is a single POST /fixtures with an
 * `overwrite` flag (see story API Contract "Decisions"): "Add fixture" posts
 * overwrite=false, "Replace" posts overwrite=true with the path locked.
 */
export default function FixtureUploadDialog({
  open,
  scenarioId,
  replaceTarget,
  onClose,
  onUploaded,
}: FixtureUploadDialogProps) {
  const isReplace = replaceTarget !== undefined;

  const [role, setRole] = useState<FixtureRole>("context_files");
  const [path, setPath] = useState("");
  const [file, setFile] = useState<File>();
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{ root: FixtureRoot; path: string }>();
  const [error, setError] = useState<string>();
  const [config, setConfig] = useState<FixtureConfig>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setRole("context_files");
    setPath(isReplace ? replaceTarget.path : "");
    setFile(undefined);
    setUploading(false);
    setProgress(0);
    setResult(undefined);
    setError(undefined);
    api.getFixtureConfig().then(setConfig).catch(() => setConfig(undefined));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isReplace, replaceTarget?.path]);

  if (!open) return null;

  const root: FixtureRoot = isReplace ? replaceTarget.root : roleRoot(role);
  const pathError =
    !isReplace && path && (path.includes("..") || path.startsWith("/") || path.includes("\\"))
      ? `Invalid path: "${path}" resolves outside the fixtures directory. Use a relative path without ".." segments.`
      : undefined;
  const sizeError =
    file && config && file.size > config.upload_max_bytes
      ? `File exceeds the ${formatSize(config.upload_max_bytes)} limit for fixtures. Choose a smaller file or split it.`
      : undefined;
  const canUpload = !uploading && !!file && !!path.trim() && !pathError && !sizeError && !result;

  function pickFile(f: File | undefined) {
    setError(undefined);
    setFile(f);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) pickFile(e.dataTransfer.files[0]);
  }

  async function doUpload() {
    if (!file) return;
    setUploading(true);
    setProgress(0);
    setError(undefined);
    // fetch() has no native upload-progress event; simulate a short indeterminate
    // ramp so the "uploading" state (mockup state 3) is visible for small/local
    // uploads too, then jump to 100% on completion.
    const tick = setInterval(() => setProgress((p) => Math.min(p + 12, 90)), 120);
    try {
      const uploaded = await api.uploadFixture(root, path.trim(), file, isReplace);
      setProgress(100);
      setResult({ root: uploaded.root, path: uploaded.path });
      onUploaded();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError(String(e));
      }
    } finally {
      clearInterval(tick);
      setUploading(false);
    }
  }

  const title = isReplace ? "Replace fixture" : "Add fixture";
  const subtitle = isReplace ? `${replaceTarget.root}/${replaceTarget.path}` : scenarioId;

  const footer = result ? (
    <>
      <span className="footer-link">The fixtures list refreshes automatically.</span>
      <button onClick={onClose}>Done</button>
    </>
  ) : (
    <>
      <span className="footer-link">
        {isReplace
          ? `Used by ${replaceTarget.usedBy.length} scenario${replaceTarget.usedBy.length === 1 ? "" : "s"}.`
          : "Path is validated server-side (no traversal, stays under the fixtures directory)."}
      </span>
      <div className="row-actions">
        <button className="secondary" onClick={onClose} disabled={uploading}>Cancel</button>
        <button onClick={doUpload} disabled={!canUpload}>
          {uploading ? "Uploading…" : isReplace ? "Replace" : "Upload"}
        </button>
      </div>
    </>
  );

  return (
    <DetailModal
      title={title}
      subtitle={subtitle}
      open={open}
      loading={false}
      onClose={uploading ? () => {} : onClose}
      footer={footer}
    >
      {result ? (
        <>
          <div className="file-chip">
            <span className="fc-name">{file?.name}</span>
            <span className="fc-size">{file ? formatSize(file.size) : ""}</span>
          </div>
          <div className="alert alert-ok">
            <span>&#10003;</span>
            <span>
              Fixture saved to {result.root}/{result.path}. It is now available to any scenario
              referencing this path.
            </span>
          </div>
        </>
      ) : (
        <>
          {!isReplace && (
            <>
              <label className="field-label">Role</label>
              <div className="radio-row">
                {ROLE_OPTIONS.map((opt) => (
                  <label key={opt.value}>
                    <input
                      type="radio"
                      name="fixture-role"
                      checked={role === opt.value}
                      disabled={uploading}
                      onChange={() => setRole(opt.value)}
                    />
                    {opt.label}
                  </label>
                ))}
              </div>

              <label className="field-label">Target path (relative to {root} dir)</label>
              <input
                className="text-input"
                type="text"
                placeholder="e.g. stories/signup.md"
                value={path}
                disabled={uploading}
                onChange={(e) => setPath(e.target.value)}
                style={pathError ? { borderColor: "var(--fail)" } : undefined}
              />
            </>
          )}

          {isReplace && (
            <>
              <label className="field-label">Target path</label>
              <input
                className="text-input"
                type="text"
                value={`${replaceTarget.root}/${replaceTarget.path}`}
                disabled
                style={{ opacity: 0.6 }}
              />
              <div className="alert alert-warn">
                <span>&#9432;</span>
                <span>
                  This will overwrite the current content of this fixture. Scenarios referencing
                  it will use the new content on their next run.
                </span>
              </div>
              <label className="field-label">New file</label>
            </>
          )}

          <div
            className={`dropzone${dragOver ? " dragover" : ""}`}
            onClick={() => !uploading && fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <div>Drag a file here or click to browse</div>
            <div className="dz-hint">
              {isReplace
                ? `Replaces ${replaceTarget.root}/${replaceTarget.path} · max ${config ? formatSize(config.upload_max_bytes) : "5 MB"}`
                : `Text fixtures recommended (${config?.text_extensions.join(", ") ?? ".md, .txt, .json, .yaml"}) · max ${config ? formatSize(config.upload_max_bytes) : "5 MB"}`}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: "none" }}
              disabled={uploading}
              onChange={(e) => pickFile(e.target.files?.[0])}
            />
          </div>

          {file && (
            <div className="file-chip" style={sizeError ? { borderColor: "var(--fail)" } : undefined}>
              <span className="fc-name">{file.name}</span>
              <span className="fc-size" style={sizeError ? { color: "var(--fail)" } : undefined}>
                {formatSize(file.size)}
              </span>
              {!uploading && (
                <button className="icon-btn" title="Remove selection" onClick={() => pickFile(undefined)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>
          )}

          {uploading && (
            <>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.4rem" }}>
                Uploading… {progress}%
              </p>
            </>
          )}

          {pathError && (
            <div className="alert alert-error">
              <span>&#9888;</span>
              <span>{pathError}</span>
            </div>
          )}
          {sizeError && (
            <div className="alert alert-error">
              <span>&#9888;</span>
              <span>{sizeError}</span>
            </div>
          )}
          {error && (
            <div className="alert alert-error">
              <span>&#9888;</span>
              <span>{error}</span>
            </div>
          )}
        </>
      )}
    </DetailModal>
  );
}
