# Roadmap

Priorities come from the measured gaps in [RESULTS.md](RESULTS.md).

## Next

1. **Measure the LLM path.** Run `make eval` with an Anthropic key and with an Ollama model, and fill the TriageAI column of the results table.
2. **Trained name recognition for PII masking.** Rule-based name masking leaked every name on the held-out set. Add an NER-based recogniser (for example Microsoft Presidio with a multilingual model) behind the same `mask_pii` interface, and keep the leak test as the acceptance check.
3. **Time trial with real staff.** Time 20 complaints triaged by hand and 20 reviewed in TriageAI, and replace the estimate in RESULTS.md with measured minutes.
4. **Calibrate urgency on real decisions.** Use the audit log (edits to urgency) to tune the score weights instead of hand-set values.

## Good first issues

Each item is small, has a clear test, and is labelled `good first issue`.

| # | Label | Task | Done when |
|---|---|---|---|
| 1 | `good first issue` | **Hide place names from the classifier.** Replace known location names with a placeholder before TF-IDF classification (error case 2 in RESULTS.md: a lift complaint at the ECE block was classified as a washroom issue). | `make eval-category` shows no drop in accuracy and the C0308 example is classified correctly. |
| 2 | `good first issue` | **Merge near-identical reports across sub-issues.** Allow a likely duplicate when raw text similarity is very high (for example above 0.95) even if the predicted sub-issue differs (error case 4). | A unit test in `tests/test_duplicates.py` covers it and `make eval-dupes` recall does not fall. |
| 3 | `good first issue` | **Show times in the viewer's time zone.** The API returns naive timestamps, so the deployed demo shows UTC. Return ISO 8601 with an offset and format it in the browser. | The detail page shows local time; an API test checks the offset. |
| 4 | `good first issue` | **Add Tamil-English and Kannada-English cases to the PII leak test.** Extend `eval/pii_leak_test.py` with new name, phone and place patterns. | `make test-pii` reports results for the new languages. |
| 5 | `good first issue` | **Cover `app/seed.py` with a test.** Seed a temporary database from a 20-row CSV and assert the counts. | Coverage for `app/seed.py` is above 0% in `make coverage`. |

## Later

- Accessible screen-reader announcements when a complaint's urgency changes in an open view.
- Role-based access for reviewers and an authenticated deployment for real data.
- Export to common ticketing systems after a human approves.
