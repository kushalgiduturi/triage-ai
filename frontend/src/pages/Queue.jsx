import { useEffect, useState } from "react";
import { api } from "../api.js";
import { ErrorLine, Field, Page, Row, Surface, Table, Td, Th, Urgency, formatTime } from "../ui.jsx";

const URGENCIES = ["Critical", "High", "Medium", "Low"];

export default function Queue() {
  const [taxonomy, setTaxonomy] = useState(null);
  const [filters, setFilters] = useState({ category: "", urgency: "", status: "pending", search: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.taxonomy().then(setTaxonomy).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
    const handle = setTimeout(() => {
      api
        .complaints({ ...params, limit: 1000 })
        .then((d) => {
          setData(d);
          setError("");
        })
        .catch((e) => setError(e.message));
    }, 200);
    return () => clearTimeout(handle);
  }, [filters]);

  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));
  const open = (id) => (window.location.hash = `#/complaints/${id}`);
  const options = (list) => [<option key="" value="">All</option>, ...list.map((o) => <option key={o} value={o}>{o}</option>)];

  return (
    <Page title="Review Queue" intro="Sorted by urgency, then by time reported, so the complaint waiting longest comes first within each level.">
      <Surface level={1}>
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Category" as="select" value={filters.category} onChange={set("category")}>
            {options(taxonomy ? Object.keys(taxonomy.categories) : [])}
          </Field>
          <Field label="Urgency" as="select" value={filters.urgency} onChange={set("urgency")}>
            {options(URGENCIES)}
          </Field>
          <Field label="Status" as="select" value={filters.status} onChange={set("status")}>
            {options(taxonomy ? taxonomy.statuses : [])}
          </Field>
          <Field label="Search" type="search" className="w-64" placeholder="Text in the complaint"
                 value={filters.search} onChange={set("search")} />
          {data && <p className="ml-auto pb-2 text-muted tabular-nums">{data.total} complaints</p>}
        </div>

        <ErrorLine error={error} />

        <div className="mt-8">
          <Table minWidth={960}>
            <thead>
              <tr>
                <Th>Urgency</Th>
                <Th>Summary</Th>
                <Th>Category</Th>
                <Th>Location</Th>
                <Th>Suggested department</Th>
                <Th align="right">Reports</Th>
                <Th align="right">Confidence</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((c) => (
                <Row key={c.id} onOpen={() => open(c.id)}>
                  <Td><Urgency level={c.urgency} /></Td>
                  <Td>
                    <span className="text-ink">{c.summary}</span>
                    <div className="mt-0.5 text-xs text-muted">#{c.id} · {formatTime(c.reported_at)}</div>
                  </Td>
                  <Td>{c.category}</Td>
                  <Td>{c.location || "–"}</Td>
                  <Td>
                    {c.suggested_department}
                    {c.needs_manual_triage && c.status === "pending" && (
                      <div className="mt-0.5 text-xs text-muted">manual triage</div>
                    )}
                  </Td>
                  <Td align="right">{c.incident_reports}</Td>
                  <Td align="right">{c.confidence.toFixed(2)}</Td>
                  <Td>{c.status}</Td>
                </Row>
              ))}
            </tbody>
          </Table>
          {data && data.items.length === 0 && <p className="py-6 text-muted">No complaints match these filters.</p>}
          {!data && !error && <p className="py-6 text-muted">Loading…</p>}
        </div>
      </Surface>
    </Page>
  );
}
