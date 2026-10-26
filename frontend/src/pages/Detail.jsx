import { motion } from "framer-motion";
import { Fragment, useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import {
  Button, ConfirmPanel, Divider, ErrorLine, Field, Page, Row, SectionLabel, Surface, Table, Td, Th, Urgency,
  changedFields, formatTime, readable, spring,
} from "../ui.jsx";

/** Masked text with [NAME]/[PHONE]/[EMAIL]/[ID] tags emphasised so redactions are visible. */
function Masked({ text }) {
  return text.split(/(\[(?:NAME|PHONE|EMAIL|ID)\])/g).map((part, i) =>
    /^\[(NAME|PHONE|EMAIL|ID)\]$/.test(part)
      ? <strong key={i} className="font-semibold text-sky-text">{part}</strong>
      : <Fragment key={i}>{part}</Fragment>,
  );
}

/** "High (score 66/100): severity 3/5 (+46), ..." -> "Score 66/100 · severity 3/5 (+46), ..." */
function oneLineReason(ai) {
  if (ai.urgency_rule) return `Safety rule: mentions ${ai.urgency_rule}.`;
  return `Score ${ai.urgency_score}/100 · ${ai.urgency_reason.replace(/^\w+ \(score \d+\/100\):\s*/, "")}`;
}

function Item({ label, children }) {
  return (
    <div className="py-3">
      <dt className="section-label">{label}</dt>
      <dd className="mt-1 text-ink">{children}</dd>
    </div>
  );
}

export default function Detail({ id, reviewer }) {
  const [c, setC] = useState(null);
  const [taxonomy, setTaxonomy] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState(null); // null | "edit" | "merge"
  const [confirm, setConfirm] = useState(null); // null | "reject" | "merge"
  const [notes, setNotes] = useState("");
  const [edit, setEdit] = useState({});
  const [mergeTarget, setMergeTarget] = useState("");

  const load = useCallback(() => api.complaint(id).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => {
    setC(null);
    setMode(null);
    setNotes("");
    setError("");
    load();
  }, [load]);
  useEffect(() => {
    api.taxonomy().then(setTaxonomy).catch(() => {});
  }, []);

  const act = async (body) => {
    setBusy(true);
    setError("");
    try {
      setC(await api.review(id, { reviewer: reviewer.trim(), notes: notes || null, ...body }));
      setMode(null);
      setNotes("");
    } catch (e) {
      setError(e.message);
    } finally {
      setConfirm(null);
      setBusy(false);
    }
  };

  if (!c) return error ? <ErrorLine error={error} /> : <p className="text-muted">Loading…</p>;

  const ai = c.ai_suggestion;
  const canAct = reviewer.trim().length >= 2 && !busy;
  const mergeCandidates = c.similar.filter((s) => !s.same_incident);
  const decision = c.human_decision;

  return (
    <Page>
      <p className="text-muted">AI suggestion only. Human decision required.</p>
      <h1 className="mt-3 text-title text-ink">{ai.summary}</h1>
      <p className="mt-2 text-muted">
        #{c.id}{c.external_id ? ` (${c.external_id})` : ""} · {c.location || "location unknown"} · reported{" "}
        {formatTime(c.reported_at)} · {c.status}
        {c.incident && c.incident.report_count > 1 ? ` · incident #${c.incident.id} with ${c.incident.report_count} reports` : ""}
      </p>

      {/* Bottom padding on narrow screens leaves room to scroll content above the bottom sheet. */}
      <div className="mt-8 grid items-start gap-8 pb-[52vh] lg:grid-cols-[minmax(0,1fr)_380px] lg:pb-0">
        {/* Level 1: the complaint itself */}
        <Surface level={1}>
          <div className="space-y-7">
            <div>
              <SectionLabel>Original text</SectionLabel>
              <p className="mt-2 whitespace-pre-wrap leading-relaxed">{c.text}</p>
              {c.contact && <p className="mt-2 text-muted">Contact (never sent to the AI): {c.contact}</p>}
            </div>
            <div>
              <SectionLabel>Masked text sent to the AI</SectionLabel>
              <p className="mt-2 whitespace-pre-wrap leading-relaxed"><Masked text={c.masked_text} /></p>
              <p className="mt-1 text-xs text-muted">
                {c.pii_types.length ? `Masked before any AI call: ${c.pii_types.join(", ")}` : "No personal data detected."}
              </p>
            </div>
            <div>
              <SectionLabel>AI summary</SectionLabel>
              <p className="mt-2">{ai.summary}</p>
              <p className="mt-2 text-muted">{ai.reasoning}</p>
              <p className="mt-1 text-xs text-muted">
                {ai.method === "llm" ? "Claude" : "Offline classifier"} · safety risk {ai.safety_risk ? "yes" : "no"} ·{" "}
                {ai.people_affected} affected · sentiment {ai.sentiment} · severity {ai.severity}/5
              </p>
            </div>
          </div>

          <Divider className="my-8" />

          <SectionLabel id="similar">Similar and duplicate complaints</SectionLabel>
          {c.similar.length === 0 && <p className="mt-2 text-muted">No complaint is more than 65% similar.</p>}
          <ul className="mt-2" aria-labelledby="similar">
            {c.similar.map((s) => (
              <li key={s.id} className="grid grid-cols-[7.5rem_1fr] gap-4 border-b border-line py-4 last:border-b-0">
                <div>
                  <div className="text-lg font-semibold tabular-nums">{Math.round(s.similarity * 100)}%</div>
                  <div className="text-xs text-muted">
                    {s.label === "likely_duplicate" ? "likely duplicate" : "related"}
                    {s.same_incident ? " · same incident" : ""}
                  </div>
                </div>
                <div>
                  <a href={`#/complaints/${s.id}`} className="link">#{s.id}</a> <span>{s.masked_text}</span>
                  <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted">
                    <span>{s.location}</span><span>·</span><span>{s.category}</span><span>·</span>
                    <Urgency level={s.urgency} /><span>·</span><span>{s.status}</span><span>·</span>
                    <span>{formatTime(s.reported_at)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <Divider className="my-8" />

          <SectionLabel>History</SectionLabel>
          <div className="mt-2">
            <Table minWidth={560}>
              <thead>
                <tr><Th>Time</Th><Th>Reviewer</Th><Th>Action</Th><Th>Old value</Th><Th>New value</Th></tr>
              </thead>
              <tbody>
                {c.audit_log.map((a, i) => {
                  const diff = changedFields(a.old_value, a.new_value);
                  return (
                    <Row key={i}>
                      <Td className="whitespace-nowrap">{formatTime(a.timestamp)}</Td>
                      <Td>{a.reviewer}</Td>
                      <Td>{readable(a.action)}</Td>
                      <Td className="text-muted">{diff.old}</Td>
                      <Td>{diff.new}</Td>
                    </Row>
                  );
                })}
              </tbody>
            </Table>
          </div>
        </Surface>

        {/* Level 2: the decision panel. Sticky on wide screens, a bottom sheet on narrow ones. */}
        <motion.aside
          aria-label="Recommendation and decision"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={spring}
          className="surface-2 fixed inset-x-0 bottom-0 z-30 max-h-[50vh] overflow-y-auto !rounded-b-none p-6 sm:p-7
                     lg:sticky lg:inset-auto lg:top-28 lg:z-auto lg:max-h-[calc(100vh-8rem)] lg:!rounded-[24px]"
        >
          <SectionLabel>Recommendation</SectionLabel>
          <dl className="mt-1 divide-y divide-line">
            <Item label="Category">{ai.category} / {readable(ai.sub_issue)}</Item>
            <Item label="Urgency">
              <Urgency level={c.urgency} />
              <span className="mt-1 block text-muted">{oneLineReason(ai)}</span>
            </Item>
            <Item label="Recommended department">
              {ai.department}
              {c.needs_manual_triage && <span className="block text-muted">Queued for manual triage: confidence below 0.60</span>}
            </Item>
            <Item label="SLA">{ai.sla_hours} {ai.sla_hours === 1 ? "hour" : "hours"}</Item>
            <Item label="Next action">{ai.next_action}</Item>
            <Item label="Confidence">
              <span className="tabular-nums">{ai.confidence.toFixed(2)}</span>
              <div className="mt-2 h-1.5 w-full rounded-full bg-mist">
                <div className="h-1.5 rounded-full bg-sky" style={{ width: `${Math.round(ai.confidence * 100)}%` }} />
              </div>
            </Item>
          </dl>

          <Divider className="my-4" />

          <SectionLabel>Decision</SectionLabel>
          <p className="mt-1">
            {decision.reviewer
              ? `${c.status} by ${decision.reviewer}, ${formatTime(decision.reviewed_at)}` +
                (decision.department ? ` · ${decision.department}` : "") +
                (decision.urgency ? ` · ${decision.urgency}` : "")
              : "Pending. Nothing is sent to any department until a reviewer decides."}
          </p>

          {mode === "edit" && taxonomy && (
            <div className="mt-4 grid gap-3">
              <Field label="Category" as="select" value={edit.category}
                     onChange={(e) => setEdit({ ...edit, category: e.target.value, sub_issue: taxonomy.categories[e.target.value][0] })}>
                {Object.keys(taxonomy.categories).map((o) => <option key={o} value={o}>{o}</option>)}
              </Field>
              <Field label="Sub-issue" as="select" value={edit.sub_issue} onChange={(e) => setEdit({ ...edit, sub_issue: e.target.value })}>
                {taxonomy.categories[edit.category].map((o) => <option key={o} value={o}>{readable(o)}</option>)}
              </Field>
              <Field label="Urgency" as="select" value={edit.urgency} onChange={(e) => setEdit({ ...edit, urgency: e.target.value })}>
                {["Critical", "High", "Medium", "Low"].map((o) => <option key={o} value={o}>{o}</option>)}
              </Field>
              <Field label="Department" as="select" value={edit.department} onChange={(e) => setEdit({ ...edit, department: e.target.value })}>
                {taxonomy.departments.filter((d) => d !== "Needs manual triage").map((o) => <option key={o} value={o}>{o}</option>)}
              </Field>
            </div>
          )}

          {mode === "merge" && (
            <div className="mt-4 grid gap-3">
              <Field label="Merge into" as="select" value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)}>
                <option value="">Choose a similar complaint</option>
                {mergeCandidates.map((s) => (
                  <option key={s.id} value={s.id}>#{s.id} · {Math.round(s.similarity * 100)}% · {s.summary}</option>
                ))}
              </Field>
              <Field label="Or complaint ID" type="number" min="1" value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)} />
            </div>
          )}

          <Field label="Notes (optional)" className="mt-4" value={notes} onChange={(e) => setNotes(e.target.value)} />

          <div className="mt-5 flex flex-wrap gap-2">
            {mode === null && (
              <>
                <Button variant="primary" disabled={!canAct} onClick={() => act({ action: "approve" })}>Approve</Button>
                <Button disabled={!canAct} onClick={() => {
                  setEdit({ category: c.category, sub_issue: c.sub_issue, urgency: c.urgency, department: ai.department });
                  setMode("edit");
                }}>Edit</Button>
                <Button disabled={!canAct} onClick={() => setConfirm("reject")}>Reject</Button>
                <Button disabled={!canAct} onClick={() => { setMergeTarget(mergeCandidates[0]?.id ?? ""); setMode("merge"); }}>Merge</Button>
              </>
            )}
            {mode === "edit" && (
              <>
                <Button variant="primary" disabled={!canAct} onClick={() => act({ action: "edit", ...edit })}>Save edit</Button>
                <Button onClick={() => setMode(null)}>Cancel</Button>
              </>
            )}
            {mode === "merge" && (
              <>
                <Button variant="primary" disabled={!canAct || !mergeTarget} onClick={() => setConfirm("merge")}>Merge</Button>
                <Button onClick={() => setMode(null)}>Cancel</Button>
              </>
            )}
          </div>
          {!reviewer.trim() && <p className="mt-3 text-muted">Enter your name in the Reviewer field at the top to act.</p>}
          <ErrorLine error={error} />
        </motion.aside>
      </div>

      <ConfirmPanel open={confirm === "reject"} title="Reject this complaint?" confirmLabel="Reject"
                    onCancel={() => setConfirm(null)} onConfirm={() => act({ action: "reject" })}>
        It leaves the queue as rejected. The decision is recorded in the audit log under your name.
      </ConfirmPanel>
      <ConfirmPanel open={confirm === "merge"} title={`Merge into complaint #${mergeTarget}?`} confirmLabel="Merge"
                    onCancel={() => setConfirm(null)} onConfirm={() => act({ action: "merge", merge_into: Number(mergeTarget) })}>
        This complaint joins that complaint's incident and leaves the pending queue. The incident's report count and
        urgency are recalculated.
      </ConfirmPanel>
    </Page>
  );
}
