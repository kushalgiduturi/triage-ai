import { useEffect, useState } from "react";
import { api } from "../api.js";
import { ErrorLine, Field, Page, Row, Surface, Table, Td, Th, changedFields, formatTime, readable } from "../ui.jsx";

export default function AuditLog() {
  const [includeAi, setIncludeAi] = useState("false");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setRows(null);
    api.audit({ include_ai: includeAi, limit: 500 }).then((d) => setRows(d.items)).catch((e) => setError(e.message));
  }, [includeAi]);

  return (
    <Page title="Audit Log" intro="Every human decision, newest first, with the value before and after.">
      <Surface level={1}>
        <Field label="Show" as="select" className="w-80" value={includeAi} onChange={(e) => setIncludeAi(e.target.value)}>
          <option value="false">Human actions</option>
          <option value="true">Human actions and AI suggestions</option>
        </Field>

        <ErrorLine error={error} />

        <div className="mt-8">
          <Table caption="Audit log of reviewer actions">
            <thead>
              <tr><Th>Timestamp</Th><Th>Reviewer</Th><Th>Action</Th><Th>Complaint</Th><Th>Old value</Th><Th>New value</Th></tr>
            </thead>
            <tbody>
              {rows?.map((a) => {
                const diff = changedFields(a.old_value, a.new_value);
                return (
                  <Row key={a.id}>
                    <Td className="whitespace-nowrap">{formatTime(a.timestamp)}</Td>
                    <Td>{a.reviewer}</Td>
                    <Td>{readable(a.action)}</Td>
                    <Td><a className="link" href={`#/complaints/${a.complaint_id}`}>#{a.complaint_id}</a></Td>
                    <Td className="text-muted">{diff.old}</Td>
                    <Td>{diff.new}</Td>
                  </Row>
                );
              })}
            </tbody>
          </Table>
          {rows && rows.length === 0 && <p className="py-6 text-muted">No reviewer actions yet.</p>}
          {!rows && !error && <p className="py-6 text-muted">Loading…</p>}
        </div>
      </Surface>
    </Page>
  );
}
