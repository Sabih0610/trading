"""Hostile repository scan for execution surfaces prohibited by project policy."""

import re

from tb.core.config import repo_root


def test_runtime_source_contains_no_forbidden_product_endpoints() -> None:
    forbidden = {
        r"\bfut" + r"ures\b": "leveraged contract product",
        r"\bperpet" + r"uals?\b": "perpetual contract product",
        r"\bmargin\b": "borrowed-funds product",
        r"\boptions?\b": "option product",
        r"\bearn\b": "yield product",
        r"\bloans?\b": "lending product",
        r"\bstaking\b": "staking product",
        r"\bleverage\b": "leverage setting",
        r"short[_ -]?sell": "unowned-sale path",
        r"position[_ -]?side\s*[:=]\s*[\"']?short": "short position direction",
    }
    source_dir = repo_root() / "src"
    violations: list[str] = []

    for path in sorted(source_dir.rglob("*.py")):
        content = path.read_text(encoding="utf-8")
        for pattern, reason in forbidden.items():
            if re.search(pattern, content, flags=re.IGNORECASE):
                violations.append(f"{path.relative_to(repo_root())}: {reason}")

    assert violations == [], "Forbidden execution surface found:\n" + "\n".join(violations)
