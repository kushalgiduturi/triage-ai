import { useEffect, useState } from "react";
import { api } from "../api.js";
import { BarList, Divider, ErrorLine, Figure, Page, Row, SectionLabel, Surface, Table, Td, Th, pct, readable } from "../ui.jsx";

const URGENCY_ORDER = ["Critical", "High", "Medium", "Low"];

export default function Analytics() {
  const [m, setM] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.metrics().then(setM).catch((e) => setError(e.message));
  }, []);

  if (!m) return error ? <ErrorLine error={error} /> : <p className="text-muted">Loading…</p>;

  const acc = m.accuracy_vs_ground_truth;
  const human = m.human_agreement;
  const dist = m.distributions;
  const ev = m.offline_evaluation;
  const total = Object.values(dist.status).reduce((a, b) => a + b, 0);
  const categories = Object.entries(dist.category).map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
  const urgency = URGENCY_ORDER.map((label) => ({ label, value: dist.urgency[label] || 0 }));
  const agreement = [
    { label: "Category kept", value: human.category_agreement },
    { label: "Urgency kept", value: human.urgency_agreement },
    { label: "Department kept", value: human.department_agreement },
  ].filter((r) => r.value !== null);
  const incidents = m.incidents.largest.map((i) => ({ label: `${i.title.replace(/\.$/, "")} (#${i.id})`, value: i.reports }));

  return (
    <Page title="Analytics">
      <Surface level={1}>
        <div className="flex flex-wrap gap-x-14 gap-y-8">
          <Figure label="Complaints" value={total} />
          <Figure label="Pending review" value={dist.status.pending || 0} />
          <Figure label="Multi-report incidents" value={m.incidents.multi_report_incidents} />
          <Figure label="Category accuracy" value={pct(acc.category_accuracy)} />
          <Figure label="Routing accuracy" value={pct(acc.routing_accuracy)} />
          <Figure label="Manual triage rate" value={pct(acc.manual_triage_rate)} />
        </div>
        <p className="mt-4 text-xs text-muted">
          Accuracy is measured against the ground-truth labels of {acc.n_labelled} synthetic complaints.
        </p>

        <Divider className="my-10" />

        <div className="grid gap-12 xl:grid-cols-2">
          <div>
            <SectionLabel>Category distribution</SectionLabel>
            <div className="mt-4"><BarList rows={categories} /></div>
          </div>
          <div>
            <SectionLabel>Urgency distribution</SectionLabel>
            <div className="mt-4"><BarList rows={urgency} labelWidth="6rem" /></div>
          </div>
        </div>

        <Divider className="my-10" />

        <div className="grid gap-12 xl:grid-cols-2">
          <div>
            <SectionLabel>Human agreement</SectionLabel>
            <div className="mt-4 flex flex-wrap gap-x-12 gap-y-6">
              <Figure label="Approved without changes" value={pct(human.agreement_rate)} />
              <Figure label="Reviewed" value={human.n_reviewed} />
              <Figure label="Edited" value={human.n_edited} />
              <Figure label="Rejected or merged" value={human.n_rejected + human.n_merged} />
            </div>
            {agreement.length > 0 ? (
              <div className="mt-6"><BarList rows={agreement} max={1} format={(v) => pct(v)} labelWidth="9rem" /></div>
            ) : (
              <p className="mt-6 text-muted">No reviews yet. Agreement appears once reviewers approve or edit suggestions.</p>
            )}
          </div>
          <div>
            <SectionLabel>Duplicate incidents</SectionLabel>
            <p className="mt-2 text-muted">
              {m.incidents.complaints_in_multi_report_incidents} complaints grouped into{" "}
              {m.incidents.multi_report_incidents} incidents with two or more reports. Largest:
            </p>
            <div className="mt-4"><BarList rows={incidents} labelWidth="minmax(0, 18rem)" /></div>
          </div>
        </div>

        <Divider className="my-10" />

        <SectionLabel>Bias check by writing style</SectionLabel>
        <p className="mt-2 max-w-3xl text-muted">
          Large gaps between rows would mean the way someone writes changes how they are treated.
        </p>
        <div className="mt-4">
          <Table minWidth={760}>
            <thead>
              <tr>
                <Th>Style</Th><Th align="right">Complaints</Th><Th align="right">Mean urgency score</Th>
                <Th align="right">Critical</Th><Th align="right">Manual triage</Th>
                <Th align="right">Category accuracy</Th><Th align="right">Urgency accuracy</Th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(m.bias_by_language_style).map(([style, b]) => (
                <Row key={style}>
                  <Td>{readable(style)}</Td>
                  <Td align="right">{b.n}</Td>
                  <Td align="right">{b.mean_urgency_score}</Td>
                  <Td align="right">{pct(b.critical_rate)}</Td>
                  <Td align="right">{pct(b.manual_triage_rate)}</Td>
                  <Td align="right">{pct(b.category_accuracy)}</Td>
                  <Td align="right">{pct(b.urgency_accuracy)}</Td>
                </Row>
              ))}
            </tbody>
          </Table>
        </div>
        {ev?.bias_check && (
          <p className="mt-4">
            Rewrite test: urgency stayed identical for <strong>{pct(ev.bias_check.consistency)}</strong> of{" "}
            {ev.bias_check.n_complaints} complaints across {ev.bias_check.n_variants} tone and dialect versions each
            ({ev.bias_check.rewriter}).
          </p>
        )}

        {ev && (
          <>
            <Divider className="my-10" />
            <SectionLabel>Offline evaluation</SectionLabel>
            <p className="mt-2 text-muted">eval/evaluate.py · {ev.mode} · {ev.n} complaints · {ev.generated_at.replace("T", " ")}</p>
            <div className="mt-5 flex flex-wrap gap-x-14 gap-y-8">
              <Figure label="Category accuracy" value={pct(ev.category_accuracy, 1)} />
              <Figure label="Urgency macro-F1" value={ev.urgency_macro_f1.toFixed(2)} />
              <Figure label="Duplicate precision" value={ev.duplicates.precision.toFixed(2)} />
              <Figure label="Duplicate recall" value={ev.duplicates.recall.toFixed(2)} />
              <Figure label="Routing accuracy" value={pct(ev.routing_accuracy, 1)} />
            </div>
          </>
        )}
      </Surface>
    </Page>
  );
}
