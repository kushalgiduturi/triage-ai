import { MotionConfig } from "framer-motion";
import { useEffect, useState } from "react";
import Queue from "./pages/Queue.jsx";
import Detail from "./pages/Detail.jsx";
import Submit from "./pages/Submit.jsx";
import Analytics from "./pages/Analytics.jsx";
import AuditLog from "./pages/AuditLog.jsx";
import { Surface } from "./ui.jsx";

// Hash routing keeps UI routes (#/complaints/12) from colliding with API routes (/complaints/12)
// when FastAPI serves both from the same origin.
function parseHash() {
  const path = window.location.hash.replace(/^#/, "") || "/";
  const detail = path.match(/^\/complaints\/(\d+)/);
  if (detail) return { page: "detail", id: Number(detail[1]) };
  if (path.startsWith("/submit")) return { page: "submit" };
  if (path.startsWith("/analytics")) return { page: "analytics" };
  if (path.startsWith("/audit")) return { page: "audit" };
  return { page: "queue" };
}

const NAV = [
  { page: "queue", href: "#/", label: "Queue" },
  { page: "submit", href: "#/submit", label: "Submit" },
  { page: "analytics", href: "#/analytics", label: "Analytics" },
  { page: "audit", href: "#/audit", label: "Audit Log" },
];

export default function App() {
  const [route, setRoute] = useState(parseHash);
  const [reviewer, setReviewer] = useState(() => localStorage.getItem("reviewer") || "");

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHash());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => localStorage.setItem("reviewer", reviewer), [reviewer]);

  const active = route.page === "detail" ? "queue" : route.page;

  return (
    // reducedMotion="user": with prefers-reduced-motion, Framer drops transforms and keeps opacity changes.
    <MotionConfig reducedMotion="user">
      {/* Level 0 ambience: one static, very soft sky bloom behind the content. */}
      <div aria-hidden="true" className="ambient-bloom pointer-events-none fixed inset-x-0 top-0 -z-10 h-[620px]" />

      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-pill focus:bg-white focus:px-4 focus:py-2">
        Skip to content
      </a>

      {/* Floating navigation dock: the only fixed element. */}
      <header className="fixed inset-x-0 top-4 z-40 flex justify-center px-4">
        <Surface as="nav" level={1} shape="pill" padded={false} aria-label="Main"
                 className="flex max-w-full items-center gap-1 py-1.5 pl-5 pr-1.5">
          <a href="#/" className="mr-3 font-semibold tracking-tight text-ink">TriageAI</a>
          {NAV.map((item) => (
            <a
              key={item.page}
              href={item.href}
              aria-current={active === item.page ? "page" : undefined}
              className={
                "rounded-pill px-3.5 py-1.5 " +
                (active === item.page ? "bg-mist font-medium text-sky-text" : "text-ink hover:text-sky-text")
              }
            >
              {item.label}
            </a>
          ))}
          <label htmlFor="reviewer" className="ml-3 hidden text-xs text-muted md:block">Reviewer</label>
          <input
            id="reviewer"
            className="ml-2 w-36 rounded-pill border border-line bg-white px-3 py-1.5 text-ink"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="Your name"
            aria-label="Reviewer name"
          />
        </Surface>
      </header>

      <main id="main" className="mx-auto max-w-content px-4 pb-24 pt-28 sm:px-8">
        {/* Keyed so each route mounts fresh and plays the Page fade + 8px rise. */}
        <div key={route.page + (route.id ?? "")}>
            {route.page === "queue" && <Queue />}
            {route.page === "detail" && <Detail id={route.id} reviewer={reviewer} />}
            {route.page === "submit" && <Submit />}
            {route.page === "analytics" && <Analytics />}
            {route.page === "audit" && <AuditLog />}
        </div>
      </main>
    </MotionConfig>
  );
}
