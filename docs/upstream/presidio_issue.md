# Draft issue for data-privacy-stack/presidio (not posted)

Repository: https://github.com/data-privacy-stack/presidio (formerly microsoft/presidio)
Status: draft, waiting for approval before posting.

---

**Title:** Valid Indian mobile numbers score DATE_TIME (0.85) above PHONE_NUMBER and are anonymized as `<DATE_TIME>`

**Describe the bug**

With the default `AnalyzerEngine` (spaCy `en_core_web_lg`), a valid Indian mobile number is returned as both `PHONE_NUMBER` and `DATE_TIME`, and `DATE_TIME` gets the higher score (0.85, against 0.4 for `PHONE_NUMBER`, or 0.75 with a context word). `AnonymizerEngine` keeps the higher-scoring result, so the number is replaced with `<DATE_TIME>`. The same sentence with a US number does not produce `DATE_TIME` at all.

**To Reproduce**

```python
from presidio_analyzer import AnalyzerEngine
text = "Call me on 9848012345 about the water problem."
for r in AnalyzerEngine().analyze(text=text, language="en"):
    print(r.entity_type, text[r.start:r.end], round(r.score, 2))
```

Output:

```
DATE_TIME 9848012345 0.85
PHONE_NUMBER 9848012345 0.4
US_BANK_NUMBER 9848012345 0.05
US_DRIVER_LICENSE 9848012345 0.01
```

Passing these results to `AnonymizerEngine().anonymize(...)` returns `Call me on <DATE_TIME> about the water problem.`

The number is valid: `phonenumbers.is_valid_number(phonenumbers.parse("9848012345", "IN"))` is `True`, and `IN` is in `PhoneRecognizer.DEFAULT_SUPPORTED_REGIONS`.

**Expected behavior**

A number that `PhoneRecognizer` matched and validated for a supported region should be the top-scoring entity, so it is anonymized as `<PHONE_NUMBER>`.

**More detail**

Top-scoring entity for the same sentence with different numbers:

| Number | Top entity (score) | PHONE_NUMBER score |
|---|---|---|
| `9848012345` (India) | DATE_TIME (0.85) | 0.4 |
| `+91 9848012345` (India) | DATE_TIME (0.85) | 0.4 |
| `98480 12345` (India) | DATE_TIME (0.85) | 0.4 |
| `07700 900123` (UK) | DATE_TIME (0.85) | 0.4 |
| `2025550143` (US) | PHONE_NUMBER (0.4) | 0.4 |
| `(202) 555-0143` (US) | PHONE_NUMBER (0.4) | 0.4 |

Context words raise `PHONE_NUMBER` but not above `DATE_TIME`: `My phone number is 9848012345.` gives DATE_TIME 0.85 and PHONE_NUMBER 0.75, while `My phone number is 2025550143.` gives PHONE_NUMBER 0.75 only.

A related observation: `"call"` is in `PhoneRecognizer.CONTEXT`, but `Call me on 9848012345 ...` and `please call 9848012345 today` keep PHONE_NUMBER at 0.4, while `phone` and `mobile` raise it to 0.75.

On a set of 240 synthetic complaints in Hinglish, Telugu-English and Indian English containing 203 phone numbers, the top-scoring label for each number was: PHONE_NUMBER 153, DATE_TIME 32, PERSON 16 (a wider span that swallowed the number), UK_NHS 2.

**Possible directions** (happy to open a PR with tests for whichever you prefer)

1. In `PhoneRecognizer`, raise the score when `phonenumbers` validates the match for one of the supported regions (it already parses with that region).
2. In `SpacyRecognizer`, skip `DATE_TIME` for a span that is only digits and phone separators of phone-number length.
3. Document the behaviour and recommend removing `DATE_TIME` for text that mainly contains phone numbers.

**Related, not duplicates:** #2082 (Hinglish NER support) and #1632 (Aadhaar formats). I searched for "DATE_TIME phone" and found no existing report.

**Environment**

- presidio-analyzer 2.2.365, presidio-anonymizer 2.2.365
- spaCy 3.8.16 with en_core_web_lg 3.8.0, phonenumbers 9.0.41
- Python 3.11.9, Windows 11

**Additional context**

Found while building an open-source complaint triage tool for Indian campuses that masks PII before any LLM call: https://github.com/kushalgiduturi/triage-ai. The comparison script is `eval/presidio_compare.py`.
