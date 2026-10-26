/**
 * TriageAI design system. Every page is built from these pieces so elevation, colour,
 * type and motion stay consistent. Tokens live in tailwind.config.js and index.css.
 *
 *   Surface level={0|1|2}   0 = base page, 1 = content glass, 2 = focus glass
 *                           shape: "card" (default) | "pill" (nav dock) | "sheet" (decision panel)
 *   Button variant=primary|secondary
 *   Table / Th / Row / Td   open tables (horizontal hairlines only)
 *   Field                   label + input/select/textarea
 *
 * Motion is limited to: page fade + 8px rise, Level 2 panel entrance, clickable-row hover
 * lift (2px), button press (0.98) and the urgency cross-fade. With prefers-reduced-motion
 * every transform is dropped and only opacity changes remain.
 */
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { forwardRef, useEffect, useId, useRef } from "react";

// Functional motion only: one spring for everything (~200ms settle).
export const spring = { type: "spring", stiffness: 260, damping: 28 };

/** Returns `transform` unless the user asked for reduced motion (then no transform at all). */
export function useMotionSafe() {
  const reduce = useReducedMotion();
  return (transform) => (reduce ? {} : transform);
}

// ------------------------------------------------------------------ surfaces

const SHAPE = {
  card: { 1: "rounded-l1", 2: "rounded-l2" },
  pill: { 1: "rounded-pill", 2: "rounded-pill" },
  // Bottom sheet on narrow screens, floating Level 2 panel from lg up.
  sheet: { 1: "rounded-t-l1 lg:rounded-l1", 2: "rounded-t-l2 lg:rounded-l2" },
};

/**
 * The only way to draw an elevated surface. `as` may be a tag name or a motion component.
 * `blur={false}` keeps the Level 2 look without backdrop-filter (used over an opaque scrim so
 * no page shows more than three blurred elements).
 */
export const Surface = forwardRef(function Surface(
  { level = 1, shape = "card", blur = true, padded = true, as: Tag = "section", className = "", children, ...rest },
  ref,
) {
  if (level === 0) return <Tag ref={ref} className={className} {...rest}>{children}</Tag>;
  const elevation = level === 2 ? "surface-2" : "surface-1";
  const pad = !padded ? "" : level === 1 ? "p-8 sm:p-10" : "p-6 sm:p-7";
  return (
    <Tag ref={ref} className={`${elevation} ${SHAPE[shape][level]} ${blur ? "" : "surface-noblur"} ${pad} ${className}`} {...rest}>
      {children}
    </Tag>
  );
});

/** Page wrapper: gentle fade + 8px rise on entry (opacity only under reduced motion). */
export function Page({ title, intro, children }) {
  const safe = useMotionSafe();
  return (
    <motion.div initial={{ opacity: 0, ...safe({ y: 8 }) }} animate={{ opacity: 1, ...safe({ y: 0 }) }}
                transition={spring}>
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
  const safe = useMotionSafe();
  const styles =
    variant === "primary"
      ? "bg-sky-text text-white hover:bg-sky-strong"
      : "bg-white text-ink border border-line hover:border-sky";
  return (
    <motion.button
      whileTap={safe({ scale: 0.98 })}
      transition={spring}
      className={`inline-flex items-center justify-center rounded-pill px-5 py-2 font-medium disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
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

/** Open table. Columns wrap instead of scrolling sideways, so there is no hidden overflow. */
export function Table({ children, caption }) {
  return (
    <table className="w-full border-collapse text-left">
      {caption && <caption className="sr-only">{caption}</caption>}
      {children}
    </table>
  );
}

export function Th({ children, align = "left", className = "" }) {
  return (
    <th scope="col" className={`section-label border-b border-line py-3 pr-4 font-medium ${align === "right" ? "text-right" : "text-left"} ${className}`}>
      {children}
    </th>
  );
}

// Mist (#F0F9FF) at 60%: light enough that secondary text keeps AA contrast (4.6:1) on hover.
const ROW_HOVER = "rgba(240, 249, 255, 0.6)";

/**
 * Table row. With `onOpen` the row is clickable: it lifts 2px with a light mist highlight.
 * Keyboard users reach the same action through the link inside the row, so the row itself
 * is not an extra tab stop.
 */
export function Row({ onOpen, children }) {
  const safe = useMotionSafe();
  const interactive = Boolean(onOpen);
  return (
    <motion.tr
      whileHover={interactive ? { ...safe({ y: -2 }), backgroundColor: ROW_HOVER } : undefined}
      transition={spring}
      onClick={onOpen}
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

// Low -> High: deeper sky blue text and dot. Red only for Critical. The text label is always shown.
const URGENCY_STYLE = {
  Low: { text: "text-sky-text font-normal", dot: "bg-sky" },
  Medium: { text: "text-sky-strong font-medium", dot: "bg-sky-deep" },
  High: { text: "text-sky-night font-semibold", dot: "bg-sky-night" },
  Critical: { text: "text-critical font-semibold", dot: "bg-critical" },
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
        <span aria-hidden="true" className={`inline-block h-2 w-2 rounded-pill ${style.dot}`} />
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
export function BarList({ rows, max, format = (v) => v, labelWidth = "12rem", empty = "No data yet." }) {
  if (!rows.length) return <p className="text-muted">{empty}</p>;
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="grid items-center gap-3" style={{ gridTemplateColumns: `${labelWidth} 1fr` }}>
          <div className="text-ink">{r.label}</div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 rounded-pill bg-sky" style={{ width: `${(r.value / top) * 85}%`, minWidth: 3 }} />
            <span className="tabular-nums text-ink">{format(r.value)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Destructive confirmation (Reject, Merge): a Level 2 panel over a soft white scrim.
 * Focus moves into the dialog, Tab stays inside it, and Escape or Cancel returns focus
 * to the button that opened it.
 */
export function ConfirmPanel({ open, title, children, confirmLabel, onConfirm, onCancel }) {
  const titleId = useId();
  const bodyId = useId();
  const panelRef = useRef(null);
  const returnTo = useRef(null);
  const wasOpen = useRef(false);
  const safe = useMotionSafe();

  // Remember the opener during render, before the dialog's autoFocus moves focus inside it.
  if (open && !wasOpen.current) returnTo.current = document.activeElement;
  wasOpen.current = open;

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      } else if (e.key === "Tab" && panelRef.current) {
        const items = [...panelRef.current.querySelectorAll("button:not([disabled])")];
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        } else if (!panelRef.current.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (returnTo.current && document.contains(returnTo.current)) returnTo.current.focus();
    };
  }, [open, onCancel]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onCancel}
        >
          <Surface
            as={motion.div}
            level={2}
            blur={false}
            ref={panelRef}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={bodyId}
            className="w-[30rem] max-w-full"
            initial={{ opacity: 0, ...safe({ y: 12 }) }}
            animate={{ opacity: 1, ...safe({ y: 0 }) }}
            exit={{ opacity: 0 }}
            transition={spring}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id={titleId} className="text-lg font-semibold text-ink">
              {title}
            </h2>
            <div id={bodyId} className="mt-2 text-muted">{children}</div>
            <div className="mt-6 flex justify-end gap-2">
              <Button onClick={onCancel}>Cancel</Button>
              <Button variant="primary" onClick={onConfirm} autoFocus>
                {confirmLabel}
              </Button>
            </div>
          </Surface>
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
