"""Test configuration: offline, fast, isolated.

Environment is set before any app module is imported so tests never call the
Claude API, never download the transformer model, and never touch data/triage.db.
"""

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="triageai-tests-")
os.environ.setdefault("TRIAGE_DISABLE_LLM", "1")
os.environ.setdefault("TRIAGE_EMBEDDINGS", "hash")
os.environ["TRIAGE_DATA_DIR"] = _tmp
os.environ["TRIAGE_MODELS_DIR"] = os.path.join(_tmp, "models")
