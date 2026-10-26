import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Button, Divider, ErrorLine, Field, Page, Surface, Urgency, readable } from "../ui.jsx";

export default function Submit() {
  const [form, setForm] = useState({ text: "", location: "", contact: "" });
  const [locations, setLocations] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.locations().then(setLocations).catch(() => {});
  }, []);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.submit({
        text: form.text,
        location: form.location.trim() || null,
        contact: form.contact.trim() || null,
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="Submit Complaint"
          intro="Runs the full pipeline: personal data masking, extraction, duplicate search, urgency and routing. The result is a suggestion that waits for a human reviewer.">
      <Surface level={1} className="max-w-3xl">
        <form onSubmit={submit} className="space-y-5">
          <Field label="Complaint" as="textarea" required minLength={5} rows={6}
                 placeholder="Describe the problem in any language or style" value={form.text} onChange={set("text")} />
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Location" list="known-locations" placeholder="e.g. Girls Hostel 2"
                   value={form.location} onChange={set("location")} />
            <Field label="Contact (optional, never sent to the AI)" placeholder="Phone or email"
                   value={form.contact} onChange={set("contact")} />
          </div>
          <datalist id="known-locations">
            {locations.map((l) => <option key={l} value={l} />)}
          </datalist>
          <Button type="submit" variant="primary" disabled={busy || form.text.trim().length < 5}>
            {busy ? "Submitting…" : "Submit"}
          </Button>
        </form>

        <ErrorLine error={error} />

        <div aria-live="polite">
          {result && (
            <div>
              <Divider className="my-8" />
              <p className="text-muted">AI suggestion only. Human decision required.</p>
              <h2 className="mt-2 text-lg font-semibold">Complaint #{result.id}: {result.ai_suggestion.summary}</h2>
              <dl className="mt-3 divide-y divide-line">
                <Line label="Masked text">{result.masked_text}</Line>
                <Line label="Category">{result.ai_suggestion.category} / {readable(result.ai_suggestion.sub_issue)}</Line>
                <Line label="Urgency">
                  <Urgency level={result.urgency} />
                  <span className="mt-1 block text-muted">{result.ai_suggestion.urgency_reason}</span>
                </Line>
                <Line label="Department">
                  {result.ai_suggestion.department}
                  {result.needs_manual_triage && <span className="block text-muted">Queued for manual triage: confidence below 0.60</span>}
                </Line>
                <Line label="SLA">{result.ai_suggestion.sla_hours} {result.ai_suggestion.sla_hours === 1 ? "hour" : "hours"}</Line>
                <Line label="Next action">{result.ai_suggestion.next_action}</Line>
                <Line label="Confidence">{result.confidence.toFixed(2)}</Line>
                <Line label="Duplicates">
                  {result.incident && result.incident.report_count > 1
                    ? `Joined incident #${result.incident.id}, now ${result.incident.report_count} reports`
                    : `New incident · ${result.similar.length} related complaint(s)`}
                </Line>
              </dl>
              <a className="link mt-5 inline-block" href={`#/complaints/${result.id}`}>Open the full record to review it</a>
            </div>
          )}
        </div>
      </Surface>
    </Page>
  );
}

function Line({ label, children }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[9rem_1fr] sm:gap-4">
      <dt className="section-label pt-0.5">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
