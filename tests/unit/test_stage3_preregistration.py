"""Review artifacts are exact-byte identified and preserve the owner's protocol verbatim."""

import hashlib
import re
from pathlib import Path

from tb.strategies.stage3 import CANDIDATE_TRIAL_COUNT, preregistered_trials

ROOT = Path(__file__).resolve().parents[2]


def test_registration_hash_matches_journal_and_owner_protocol_is_verbatim():
    path = ROOT / "reports/stage3/P11f-preregistration.md"
    raw = path.read_bytes()
    journal = (ROOT / "docs/journal/P11f-journal.md").read_text(encoding="utf-8")
    hashes = re.findall(r"PRE-REGISTRATION SHA-256: ([0-9a-f]{64})", journal)
    assert hashes == [hashlib.sha256(raw).hexdigest()]
    assert b"\r" not in raw
    prompt = (ROOT / "prompts/P11f-stage3-crypto.md").read_text(encoding="utf-8")
    required = prompt.split("## Part B: after approval, run the test once\n", 1)[1].split(
        "\n## Scenarios to self-test", 1
    )[0]
    assert required in raw.decode("utf-8")
    assert CANDIDATE_TRIAL_COUNT == len(preregistered_trials()) == 162
