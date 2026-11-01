"""Hostile repository scan for execution surfaces prohibited by project policy."""

import ast
import re
import sys

import pytest

from tb.core.config import repo_root

# Exact reviewed exception: Ollama generation parameters, never a product path.
_REVIEWED_LINES = {
    "src/tb/agents/providers/http.py": {'        payload["options"] = {'},
    # This literal rejects unsafe skill names; it is a denylist, not a callable surface.
    "scripts/install-skills.ps1": {
        "$Forbidden = 'derivatives|futures|margin|earn|loan|staking|options|meme|p2p|"
        "backtesting-trading-strategies'"
    },
}
_FORBIDDEN = re.compile(
    r"\bfutures\b|\bperpetuals?\b|\bmargin\b|\boptions?\b|\bearn\b|\bloans?\b|"
    r"\bstaking\b|\bleverage\b|short[_ -]?sell|"
    r"position[_ -]?side\s*[:=]\s*[\"']?short|"
    r"\b[fdse]api\b|withdraw|simple_?earn|\blending\b|flexible_?product|"
    r"/api/v3/(?:order|orderList|sor/order)|order/oco|newOrder",
    re.IGNORECASE,
)


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _constant_string(node.left), _constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def test_runtime_source_contains_no_forbidden_product_endpoints() -> None:
    root = repo_root()
    violations: list[str] = []
    for folder in ("src", "config", "scripts"):
        for path in sorted((root / folder).rglob("*")):
            if path.suffix.lower() not in {".py", ".yaml", ".yml", ".ps1"}:
                continue
            relative = path.relative_to(root).as_posix()
            content = "\n".join(
                (
                    line.replace('"options"', '"generation_parameters"')
                    if path.suffix == ".py"
                    else ""
                )
                if line in _REVIEWED_LINES.get(relative, set())
                else line
                for line in path.read_text(encoding="utf-8-sig").splitlines()
            )
            surfaces = [content]
            if path.suffix.lower() == ".py":
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        modules = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        modules = [node.module or ""]
                    else:
                        modules = []
                    if any(m.split(".")[0].lower() in {"ccxt", "binance"} for m in modules):
                        violations.append(f"{relative}: exchange SDK import")
                    value = _constant_string(node)
                    if value is not None:
                        surfaces.append(value)
            if any(_FORBIDDEN.search(surface) for surface in surfaces):
                violations.append(f"{relative}: prohibited product/order surface")
    assert violations == [], "Forbidden execution surface found:\n" + "\n".join(violations)


@pytest.mark.parametrize("suffix", [".py", ".yaml", ".ps1"])
@pytest.mark.parametrize("surface", ["DAPI", "SAPI", "simpleEarn", "/api/v3/order", "newOrder"])
def test_scanner_checks_all_runtime_formats(tmp_path, monkeypatch, suffix, surface):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / ("planted" + suffix)).write_text(f'URL = "{surface}"\n')
    monkeypatch.setattr(sys.modules[__name__], "repo_root", lambda: tmp_path)
    with pytest.raises(AssertionError):
        test_runtime_source_contains_no_forbidden_product_endpoints()
