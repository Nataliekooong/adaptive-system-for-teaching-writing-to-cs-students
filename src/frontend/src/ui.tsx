/* Notion-style UI primitives */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";

export type TagColor = "gray" | "orange" | "yellow" | "green" | "blue" | "purple" | "pink" | "red" | "brown";

export function Tag({ color = "gray", dot, children }: { color?: TagColor; dot?: boolean; children: ReactNode }) {
  return (
    <span className={`tag ${color}`}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}

export function Switch({ on, onChange, disabled, title }: {
  on: boolean; onChange?: (v: boolean) => void; disabled?: boolean; title?: string;
}) {
  return (
    <button
      type="button" title={title} role="switch" aria-checked={on} disabled={disabled}
      className={`switch ${on ? "on" : ""}`} onClick={() => onChange?.(!on)}
    />
  );
}

export function Seg<T extends string>({ value, options, onChange }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void;
}) {
  return (
    <span className="seg">
      {options.map((o) => (
        <button type="button" key={o.value} className={o.value === value ? "on" : ""} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </span>
  );
}

export interface Crumb { label: string; to?: string; icon?: string }

export function Topbar({ crumbs, right, onToggleSidebar }: {
  crumbs: Crumb[]; right?: ReactNode; onToggleSidebar?: () => void;
}) {
  const nav = useNavigate();
  return (
    <div className="topbar">
      {onToggleSidebar && (
        <button className="icon-btn" title="Toggle sidebar" onClick={onToggleSidebar}>☰</button>
      )}
      <div className="crumbs">
        {crumbs.map((c, i) => (
          <span key={i} className="row" style={{ gap: 2, minWidth: 0 }}>
            {i > 0 && <span className="crumb-sep">/</span>}
            <span className="crumb" onClick={() => c.to && nav(c.to)}>
              {c.icon && <span style={{ marginRight: 5 }}>{c.icon}</span>}
              {c.label}
            </span>
          </span>
        ))}
      </div>
      {right}
    </div>
  );
}

export function PageHeader({ icon, title, sub, children }: {
  icon: string; title: ReactNode; sub?: ReactNode; children?: ReactNode;
}) {
  return (
    <div>
      <div className="page-icon">{icon}</div>
      <h1 className="page-title">{title}</h1>
      {sub && <div className="page-sub">{sub}</div>}
      {children}
    </div>
  );
}

export function Props({ children }: { children: ReactNode }) {
  return <div className="props">{children}</div>;
}

export function Prop({ icon, label, children, editable }: {
  icon: string; label: string; children: ReactNode; editable?: boolean;
}) {
  return (
    <div className="prop">
      <div className="prop-key"><span style={{ width: 18, textAlign: "center" }}>{icon}</span>{label}</div>
      <div className={`prop-val ${editable ? "editable" : ""}`}>{children}</div>
    </div>
  );
}

export interface ViewTab { key: string; label: string; icon: string; count?: number }

export function Views({ tabs, active, onChange, right }: {
  tabs: ViewTab[]; active: string; onChange: (k: string) => void; right?: ReactNode;
}) {
  return (
    <div className="views">
      {tabs.map((t) => (
        <div key={t.key} className={`view-tab ${t.key === active ? "active" : ""}`} onClick={() => onChange(t.key)}>
          <span>{t.icon}</span>{t.label}
          {t.count !== undefined && <span className="count">{t.count}</span>}
        </div>
      ))}
      <div className="spacer" />
      {right}
    </div>
  );
}

export interface BoardColumn<T> { key: string; label: string; color: TagColor; items: T[] }

export function Board<T>({ columns, renderCard, onAdd, addLabel = "New" }: {
  columns: BoardColumn<T>[]; renderCard: (item: T) => ReactNode; onAdd?: (col: string) => void; addLabel?: string;
}) {
  return (
    <div className="board">
      {columns.map((col) => (
        <div key={col.key} className={`board-col ${col.color}`}>
          <div className="board-col-head">
            <Tag color={col.color} dot>{col.label}</Tag>
            <span className="n">{col.items.length}</span>
          </div>
          {col.items.map(renderCard)}
          {onAdd && (
            <div className="board-add" onClick={() => onAdd(col.key)}>
              <span>＋</span>{addLabel}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function Callout({ icon, color, children }: { icon: string; color?: "blue" | "yellow" | "red" | "green"; children: ReactNode }) {
  return (
    <div className={`callout ${color ?? ""}`}>
      <div className="c-ico">{icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </div>
  );
}

export function ToggleBlock({ title, children, defaultOpen = false }: {
  title: ReactNode; children: ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <div className="toggle-head" onClick={() => setOpen(!open)}>
        <span className={`caret ${open ? "open" : ""}`}>▶</span>
        <span style={{ fontWeight: 500 }}>{title}</span>
      </div>
      {open && <div className="toggle-body">{children}</div>}
    </div>
  );
}

export function Modal({ onClose, children, wide }: { onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`}>{children}</div>
    </div>
  );
}

/* ---------- toasts ---------- */
interface Toast { id: number; text: string; error?: boolean }
const ToastCtx = createContext<(text: string, error?: boolean) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, error?: boolean) => {
    const id = Math.random();
    setToasts((t) => [...t, { id, text, error }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), error ? 6000 : 3000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts">
        {toasts.map((t) => <div key={t.id} className={`toast ${t.error ? "error" : ""}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

/* ---------- data loading ---------- */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]): {
  data: T | undefined; error: string | null; reload: () => void; setData: (d: T) => void;
} {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    fn().then((d) => alive && (setData(d), setError(null))).catch((e) => alive && setError(String(e.message ?? e)));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, reload: () => setTick((t) => t + 1), setData };
}

export function Loading({ error }: { error?: string | null }) {
  return <div className="empty">{error ? `⚠️ ${error}` : "Loading…"}</div>;
}

export const STATUS_COLORS: Record<string, TagColor> = {
  draft: "gray", active: "green", paused: "yellow", completed: "blue",
  "not started": "gray", "in progress": "yellow", in_progress: "yellow", submitted: "blue", graded: "green",
  pending: "yellow", final: "green", skipped: "gray",
};
