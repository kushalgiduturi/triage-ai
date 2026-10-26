# Design decisions

Choices made where the original brief was open. All are easy to change.

## Pipeline

- **Extra extraction fields.** The schema adds `severity` (1 to 5, feeds urgency) and `confidence` (feeds routing) to the requested fields. The dataset adds `true_sub_issue` and `has_pii` columns for evaluation.
- **Constrained outputs.** The LLM chooses from enums generated from `config/departments.yaml`. A Pydantic validator rejects any sub-issue that does not belong to its category, and the API rejects reviewer edits to unknown departments. The prompt treats complaint text as untrusted data.
- **Providers.** Claude (`claude-opus-5-5`, low effort, structured outputs, server-side refusal fallback) by default; any Ollama model with `PROVIDER=ollama`. Both use the same prompt, schema and validation. Without a reachable provider the offline TF-IDF classifier is used and every result says so.
- **Seeding without a key.** The pre-seeded queue uses the offline classifier with 5-fold GroupKFold, so every seeded complaint is predicted by a model that never saw it or its duplicates.

## Duplicates

- **Issue-anchored vectors.** With raw-text embeddings only, the same incident written in English, Hinglish and Telugu-English has a median cosine of about 0.6, so the 0.85 threshold found just 20% of duplicate pairs. Each complaint vector is `embed(masked text) + embed("<category>: <sub-issue>")`, normalised.
- **Guards.** Two complaints that name different known places, have different sub-issues, or were filed more than 7 days apart can be "related" at most. "No water in Block A" and "No water in Block C" read almost the same but are different incidents.
- **Incident urgency.** All reports in an incident share its highest urgency. Report count adds 4 points (2 reports), 8 (3 or 4) or 20 (5 or more). Without a safety-rule hit or a severity-5 extraction the score is capped below Critical.

## Embeddings without torch (Lite edition)

The deployed app runs `paraphrase-multilingual-MiniLM-L12-v2` through ONNX Runtime with the 8-bit quantized export from the model's own repository, pinned to a revision. Two more memory fixes were needed to fit 512 MB on Linux:

- tokenising with SentencePiece from the same repository instead of the `tokenizers` library, which needs about 290 MB for the 250k-token vocabulary (token ids are identical for all 400 complaints);
- turning off ONNX graph optimisation, which de-quantizes weights at load time (+200 MB).

Under a hard 512 MB container limit the Lite edition uses about 350 MB after start. ONNX vectors match sentence-transformers at 0.993 mean cosine and every evaluation metric is identical.

## Review and audit

- **Statuses.** pending, approved, edited, rejected, and merged (so merged reports leave the queue while staying linked to their incident).
- **Nothing is dispatched.** Approving records a decision; there is no endpoint that sends anything anywhere.
- **Export.** `GET /export.csv` contains masked text only, never the raw complaint.

## Frontend

- **One port.** FastAPI serves the React build from `/` and the API from its own paths. Hash routes (`#/complaints/12`) keep page refreshes from colliding with the JSON route `/complaints/12`.
- **Colour contrast.** White text on `#0EA5E9` is 2.8:1 and on `#0284C7` 4.1:1, both below WCAG AA for 14px text, so buttons and sky-blue text use darker sky shades (`#0369A1`, hover `#075985`). `#0EA5E9` is used for non-text accents. Red (`#DC2626`) is reserved for Critical urgency.
- **Queue order.** Urgency first, then time reported (oldest first). The queue pages 100 rows at a time.
- **Motion.** Page fade with an 8px rise, Level 2 panel entrance, row hover lift, button press and urgency cross-fade only. With `prefers-reduced-motion` all transforms are dropped.
