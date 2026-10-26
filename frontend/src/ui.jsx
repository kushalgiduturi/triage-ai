/**
 * TriageAI design system. Every page is built from these pieces so elevation, colour,
 * type and motion stay consistent.
 *
 *   Surface level={0|1|2}   0 = base page, 1 = content glass, 2 = focus glass
 *   Button variant=primary|secondary
 *   Table / Th / Row / Td   open tables (horizontal hairlines only)
 *   Field                   label + input/select/textarea
 */
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId } from "react";

// Functional motion only: one spring for everything (~200ms settle).
export const spring = { type: "spring", stiffness: 260, damping: 28 };

// ------------------------------------------------------------------ surfaces

export function Surface({ level = 1, as: Tag = "section", className = "", children, ...rest }) {
  const base = level === 2 ? "surface-2" : level === 1 ? "surface-1" : "";
  const pad = level === 1 ? "p-8 sm:p-10" : level === 2 ? "p-6 sm:p-7" : "";
  return (
    <Tag className={`${base} ${pad} ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

/** Page wrapper: gentle fade + 8px rise on entry (opacity only under reduced motion). */
export function Page({ title, intro, children }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={spring}>
      {title && <h1 className="text-title text-ink">{title}</h1>}
      {intro && <p className="mt-2 max-w-3xl text-muted">{intro}</p>}
      <div className={title || intro ? "mt-8" : ""}>{children}</div>
    </motion.div>
  );
}

export function SectionLabel({ children, as: Tag = "h2", className = "", ...rest }) {
  return (
    <Tag className={`section-label ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

export function Divider({ className = "" }) {
  return <hr className={`border-0 border-t border-line ${className}`} />;
}

// ------------------------------------------------------------------ controls

export function Button({ variant = "secondary", className = "", children, ...rest }) {
  const styles =
    variant === "primary"
      ? "bg-sky-text text-white hover:bg-sky-strong"
      : "bg-white text-ink border border-line hover:bg-mist hover:border-sky/40";
  return (
    <motion.button
      whileTap={{ scale: 0.98 }}
      transition={spring}
      className={`inline-flex items-center justify-center rounded-full px-5 py-2 font-medium disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
      {...rest}
    >
      {children}
    </motion.button>
  );
}

/** Labelled form control. `as` = "input" | "select" | "textarea". */
export function Field({ label, as: Tag = "input", className = "", children, ...rest }) {
  const id = useId();
  return (
    <div className={`flex flex-col ${className}`}>
      <label htmlFor={id} className="section-label">
        {label}
      </label>
      <Tag id={id} className="field mt-1.5" {...rest}>
        {children}
      </Tag>
    </div>
  );
}

// ------------------------------------------------------------------ tables

export function Table({ children, minWidth = 0 }) {
  return (
    <div className="-mx-2 overflow-x-auto px-2">
      <table className="w-full border-collapse text-left" style={{ minWidth }}>
        {children}
      </table>
    </div>
  );
}

export function Th({ children, align = "left" }) {
  return (
    <th scope="col" className={`section-label border-b border-line py-3 pr-4 font-medium ${align === "right" ? "text-right" : "text-left"}`}>
      {children}
    </th>
  );
}

/** Clickable rows lift 2px with a mist highlight; Enter/Space activate them from the keyboard. */
export function Row({ onOpen, children }) {
  const interactive = Boolean(onOpen);
  return (
    <motion.tr
      whileHover={interactive ? { y: -2, backgroundColor: "#F0F9FF" } : undefined}
      transition={spring}
      onClick={onOpen}
      onKeyDown={interactive ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onOpen()) : undefined}
      tabIndex={interactive ? 0 : undefined}
      className={`border-b border-line align-top ${interactive ? "cursor-pointer" : ""}`}
    >
      {children}
    </motion.tr>
  );
}

export function Td({ children, align = "left", className = "" }) {
  return <td className={`py-3 pr-4 ${align === "right" ? "text-right tabular-nums" : "text-left"} ${className}`}>{children}</td>;
}

// ------------------------------------------------------------------ data display

const URGENCY_STYLE = {
  Low: { text: "text-sky-text font-normal", dot: "#7DD3FC" },
  Medium: { text: "text-sky-strong font-medium", dot: "#0EA5E9" },
  High: { text: "text-sky-night font-semibold", dot: "#0369A1" },
  Critical: { text: "text-critical font-semibold", dot: "#DC2626" },
};

/** Plain text urgency label with a small dot. Cross-fades when the level changes (e.g. an incident escalates). */
export function Urgency({ level }) {
  const style = URGENCY_STYLE[level] || URGENCY_STYLE.Low;
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.span
        key={level}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className={`inline-flex items-center gap-1.5 whitespace-nowrap ${style.text}`}
      >
        <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full" style={{ background: style.dot }} />
        {level}
      </motion.span>
    </AnimatePresence>
  );
}

/** A key figure: large plain number with a small label (no card). */
export function Figure({ label, value }) {
  return (
    <div>
      <div className="text-[28px] font-semibold leading-none tracking-tight text-ink tabular-nums">{value}</div>
      <div className="mt-2 text-xs text-muted">{label}</div>
    </div>
  );
}

/** Horizontal single-colour bars with the number printed at the end of each bar. */
export function BarList({ rows, max, format = (v) => v, labelWidth = "12rem" }) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="grid items-center gap-3" style={{ gridTemplateColumns: `${labelWidth} 1fr` }}>
          <div className="text-ink">{r.label}</div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 rounded-full bg-sky" style={{ width: `${(r.value / top) * 85}%`, minWidth: 3 }} />
            <span className="tabular-nums text-ink">{format(r.value)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Destructive confirmation (Reject, Merge): a Level 2 panel over a soft white scrim. */
export function ConfirmPanel({ open, title, children, confirmLabel, onConfirm, onCancel }) {
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-white/75 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onCancel}
        >
          <motion.div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="surface-2-flat w-[30rem] max-w-full p-7"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={spring}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id={titleId} className="text-lg font-semibold text-ink">
              {title}
            </h2>
            <div className="mt-2 text-muted">{children}</div>
            <div className="mt-6 flex justify-end gap-2">
              <Button onClick={onCancel}>Cancel</Button>
              <Button variant="primary" onClick={onConfirm} autoFocus>
                {confirmLabel}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function ErrorLine({ error }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-3 text-ink">
      <span className="font-semibold">Error: </span>
      {error}
    </p>
  );
}

// ------------------------------------------------------------------ formatting

export function pct(value, digits = 0) {
  return value === null || value === undefined ? "–" : `${(value * 100).toFixed(digits)}%`;
}

export function formatTime(iso) {
  if (!iso) return "–";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function readable(code) {
  return code ? code.replaceAll("_", " ") : "";
}

/** Only the fields that changed between an audit entry's old and new values. */
export function changedFields(oldValue, newValue) {
  const keys = new Set([...Object.keys(oldValue || {}), ...Object.keys(newValue || {})]);
  const changed = [...keys].filter((k) => !oldValue || JSON.stringify(oldValue[k]) !== JSON.stringify(newValue?.[k]));
  const fmt = (obj) => (obj ? changed.map((k) => `${readable(k)}: ${obj[k] ?? "–"}`).join(" · ") : "–");
  return { old: oldValue ? fmt(oldValue) : "–", new: fmt(newValue) };
}
