"""Gold exact registration bytes and owner protocol, with no data access."""

import hashlib
import re
from pathlib import Path

from tb.strategies.gold_stage3 import GOLD_TRIAL_COUNT, gold_trials

ROOT = Path(__file__).resolve().parents[2]


def test_gold_registration_bytes_and_protocol():
    raw = (ROOT / "reports/stage3/P11g-preregistration.md").read_bytes()
    journal = (ROOT / "docs/journal/P11g-journal.md").read_text(encoding="utf-8")
    assert re.findall(r"(?m)^- PRE-REGISTRATION SHA-256: ([0-9a-f]{64})", journal) == [
        hashlib.sha256(raw).hexdigest()
    ]
    assert b"\r" not in raw
    prompt = (ROOT / "prompts/P11g-stage3-gold-development.md").read_text(encoding="utf-8")
    required = prompt.split("## Part B: after approval\n", 1)[1].split(
        "\n## Scenarios to self-test", 1
    )[0]
    assert required in raw.decode("utf-8")
    assert GOLD_TRIAL_COUNT == len(gold_trials()) == 54
