# Datasheet: TriageAI synthetic complaints

Following the structure of *Datasheets for Datasets* (Gebru et al., 2021).

## Motivation

- **Purpose.** To develop and evaluate complaint triage (categorisation, urgency, duplicate detection, routing) for campus grievance cells and public-service teams without using anyone's real complaints.
- **Creator.** Generated for the TriageAI project by `data/generate_synthetic.py`.

## Composition

- **File.** `data/complaints.csv`, 400 rows, one complaint per row.
- **Fields.**

| Field | Meaning |
|---|---|
| `id` | `C0001` to `C0400`, in time order |
| `text` | The complaint as a person might write it |
| `timestamp` | Between 11 and 25 October 2026 |
| `location` | One of 22 fictional campus and town places, such as `Block A Boys Hostel` or `Ward 7 Colony` |
| `true_category` | One of 8 categories |
| `true_sub_issue` | One of 40 sub-issues |
| `true_urgency` | Low, Medium, High or Critical |
| `true_department` | From `config/departments.yaml` |
| `cluster_id` | `D01` to `D25` for planted duplicate clusters, `R01` to `R10` for related-but-different clusters, empty otherwise |
| `has_pii` | 1 if fake personal data was inserted |

- **Structure.** 25 duplicate clusters of 3 to 8 reports each (132 rows), 10 related clusters (20 rows), and 248 single complaints. 55 rows contain fake names, phone numbers, emails or roll numbers to test masking.
- **Languages and styles.** Formal English, casual English with typos, Hinglish (Hindi in Latin script) and Telugu-English, mixed within the set.
- **Label distribution.** Urgency: Medium 169, High 115, Critical 69, Low 47. Categories range from 77 (Sanitation and Cleanliness) to 24 (Academic and Administrative).
- **Personal data.** None is real. Names come from a fixed list of common Indian first names and surnames, phone numbers are random digits, and emails use reserved domains (`example.com`, `example.edu`, `example.org`).

## Collection process

- **How it was made.** The *structure* (incidents, cluster sizes, locations, timestamps, labels, which rows carry PII) is fixed by `random.Random(42)`. The *wording* comes from one of two sources: Claude, when `ANTHROPIC_API_KEY` is set (`--mode llm`), or a hand-written phrase bank with random typos and code-mixing (`data/scenarios.py`, `--mode template`).
- **The committed file was produced in template mode,** because no API key was available.
- **Ground truth** is assigned by the generator, not by human annotators. Urgency is derived from each sub-issue's base severity, an optional escalating detail (for example "more than 2 days"), and cluster size (5 or more reports raise the level by one, up to High).

## Preprocessing and uses

- No preprocessing beyond generation. PII masking happens in the application, not in the dataset.
- **Intended uses.** Development, demos, unit tests and relative comparisons between triage methods.
- **Not suitable for:** estimating real-world accuracy, training a production model, or drawing conclusions about any real institution or group of people.

## Limitations and biases

- The same person wrote the phrase bank, the keyword baseline and the rule-based parts of TriageAI, which flatters rule-based methods (see `docs/RESULTS.md`).
- Template text is far more regular than real complaints. Each sub-issue has only a few core sentences per language, so many complaints are paraphrases of each other.
- Labels reflect one designer's judgement of urgency and routing.
- Only two Indian languages are mixed in, both in Latin script; there is no Devanagari or Telugu script.

## Distribution and maintenance

- **License.** MIT, the same as the code.
- **Regenerate:** `python data/generate_synthetic.py --mode template` (deterministic) or `--mode llm` with a key (wording varies between runs).
- **Maintenance.** Open an issue for errors in the data or the datasheet.
