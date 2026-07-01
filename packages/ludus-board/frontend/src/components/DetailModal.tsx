import { useEffect } from "react";
import type { ReactNode } from "react";

export interface DetailModalProps {
  title: string;
  subtitle?: string;
  open: boolean;
  loading: boolean;
  error?: string;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
}

/**
 * Reusable read-only modal chrome (overlay/header/body/footer) shared by the
 * Scenario, Run and (future) Target detail popups. Entity-specific rendering
 * lives in `children`; this component only owns the shell + loading/error/close
 * behavior so every popup looks and behaves identically.
 */
export default function DetailModal({
  title,
  subtitle,
  open,
  loading,
  error,
  onClose,
  footer,
  children,
}: DetailModalProps) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>
            {title}
            {subtitle && <span className="modal-sub">{subtitle}</span>}
          </h2>
          <button className="icon-btn" onClick={onClose} title="Close" aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="modal-body">
          {loading && (
            <>
              <p className="muted">Loading…</p>
              <div className="skeleton" style={{ width: "60%" }} />
              <div className="skeleton" style={{ width: "40%" }} />
              <div className="skeleton" style={{ width: "80%" }} />
              <div className="skeleton" style={{ width: "50%" }} />
            </>
          )}
          {!loading && error && <p className="error">{error}</p>}
          {!loading && !error && children}
        </div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
