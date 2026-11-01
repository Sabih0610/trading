"""Independent security audit tests (Claude full audit): secrets, network, integrations, hygiene.

These tests never open external sockets and never read the contents of the root `.env`.
Known defects are kept as strict xfails tagged ``FINDING S-n`` so a fix flips them to XPASS.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import logging
import re
import shutil
import subprocess
import zipfile
from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest
from pydantic import SecretStr

from tb.core.config import Settings, features_enabled, repo_root

ROOT = repo_root()
SRC = ROOT / "src" / "tb"
SECRET = "AUDITsecretVALUE0123456789abcdef"  # fictional, high-entropy-looking sentinel


def _git(*args: str) -> str:
    if shutil.which("git") is None:
        pytest.skip("git unavailable")
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


# --------------------------------------------------------------------------- repo hygiene


def test_env_example_lists_names_only_with_empty_secret_values() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    offenders = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, sep, value = line.partition("=")
        assert sep, f"malformed .env.example line: {name}"
        if name == "OLLAMA_HOST":  # non-secret local default
            assert value in {"", "http://127.0.0.1:11434"}
            continue
        if value.strip():
            offenders.append(name)
    assert offenders == []


@pytest.mark.xfail(
    strict=True,
    reason="FINDING S-5: root .env inherits Authenticated Users:(M) "
    "and Users:(RX) ACEs; any local account can read/modify secrets "
    "(environment state; repo's own PrivateEnv.require_private refuses it)",
)
def test_root_env_acl_is_owner_and_system_only() -> None:
    env = ROOT / ".env"
    if not env.exists() or shutil.which("icacls") is None:
        pytest.skip("no root .env or not Windows")  # metadata only; contents never read
    acl = subprocess.run(["icacls", str(env)], capture_output=True, text=True).stdout
    assert not re.search(r"(?i)\\(Users|Authenticated Users|Everyone|Guests):", acl)


def test_root_env_is_ignored_and_never_tracked() -> None:
    assert subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", ".env"]).returncode == 0
    tracked = _git("ls-files").splitlines()
    assert not [
        p
        for p in tracked
        if re.fullmatch(r"(.*/)?\.env(\..*)?", p) and not p.endswith(".env.example")
    ]


def test_no_secret_shaped_files_are_tracked() -> None:
    tracked = _git("ls-files").splitlines()
    bad = [
        p
        for p in tracked
        if re.search(
            r"(?i)(\.pem|\.key|\.pfx|\.p12|id_rsa|credentials?\.json|"
            r"token\.json|\.sqlite|\.db)$",
            p,
        )
    ]
    assert bad == []


@pytest.mark.xfail(
    strict=True,
    reason="FINDING S-1: dev-kit zip/folder are tracked despite "
    ".gitignore (tracked-but-ignored files, repo hygiene)",
)
def test_no_tracked_file_matches_gitignore() -> None:
    assert _git("ls-files", "-ci", "--exclude-standard").split() == []


def test_tracked_dev_kit_zip_contains_no_secret_values() -> None:
    path = ROOT / "trading-bot-dev-kit.zip"
    if not path.exists():
        pytest.skip("zip absent")
    assignment = re.compile(
        rb"(?im)^[ \t]*([A-Z0-9_]*(KEY|SECRET|TOKEN|PASSWORD)[A-Z0-9_]*)[ \t]*=[ \t]*(\S+)"
    )
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert not [n for n in names if re.search(r"(^|/)\.env$|\.pem$|\.key$", n)]
        for name in names:
            if name.endswith("/"):
                continue
            hits = [m.group(1) for m in assignment.finditer(archive.read(name))]
            assert hits == [], f"{name} assigns a value to {hits}"


def test_git_history_has_no_high_confidence_credentials() -> None:
    history = _git("log", "--all", "-p", "--no-color")
    patterns = {
        "private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        "aws": r"AKIA[0-9A-Z]{16}",
        "openai_like": r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}",
        "xai": r"\bxai-[A-Za-z0-9]{24,}",
        "github": r"\bgh[pousr]_[A-Za-z0-9]{30,}",
        "telegram": r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}",
        "dotenv_assignment": r"(?m)^\+(?:BINANCE|FRED|FINNHUB|CRYPTOPANIC|NEWSDATA|XAI|OPENAI|DEEPSEEK|"
        r"QWEN|ANTHROPIC|JEV|TELEGRAM|MT5|OANDA|TWELVE_DATA|CTRADER)_[A-Z_]*"
        r"(?:KEY|SECRET|TOKEN)=\S{6,}",
    }
    found = {k: [m[:4] + "..." for m in re.findall(p, history)] for k, p in patterns.items()}
    assert {k: v for k, v in found.items() if v} == {}


# --------------------------------------------------------------------------- forbidden endpoints

_FORBIDDEN_EXTRA = {
    r"\bfapi\b|\bdapi\b|\beapi\b|/sapi/": "Binance derivatives/SAPI host or path",
    r"(?i)withdraw": "withdrawal",
    r"(?i)\blending\b|simple_?earn|simpleEarn|flexible_?product": "lending/earn",
    r"(?i)^\s*(import|from)\s+(ccxt|binance)\b": "exchange SDK import",
    r"/api/v3/order|/api/v3/orderList|/api/v3/sor/order": "Binance order endpoint",
    r"(?i)\border_send\b|\border_check\b|TRADE_ACTION_DEAL": "MT5 order call",
    r"(?i)ProtoOA(NewOrder|AmendOrder|ClosePosition|CancelOrder)": "cTrader order message",
    r"(?i)/v3/accounts/[^\"']*/(orders|trades|positions)/": "OANDA order/trade path",
}


def test_independent_scan_src_has_no_forbidden_or_order_surfaces() -> None:
    violations = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern, why in _FORBIDDEN_EXTRA.items():
            if re.search(pattern, text, flags=re.MULTILINE):
                violations.append(f"{path.relative_to(ROOT)}: {why}")
    assert violations == []


def _load_existing_forbidden_test():
    path = ROOT / "tests" / "scenario" / "test_forbidden_endpoints.py"
    spec = importlib.util.spec_from_file_location("_audit_forbidden_copy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "snippet",
    [
        'URL = "https://fapi.binance.com/fapi/v1/order"',
        'URL = "https://api.binance.com/sapi/v1/capital/withdraw/apply"',
        'PRODUCT = "simpleEarn"',
        'KIND = "fut" + "ures"',
        "import ccxt",
        'ORDER = "https://api.binance.com/api/v3/order"',
    ],
)
def test_existing_forbidden_scanner_catches_variants(tmp_path, monkeypatch, snippet) -> None:
    module = _load_existing_forbidden_test()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "planted.py").write_text(snippet + "\n", encoding="utf-8")
    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)
    with pytest.raises(AssertionError):
        module.test_runtime_source_contains_no_forbidden_product_endpoints()


def test_ctrader_wire_allowlist_refuses_every_order_message() -> None:
    from tb.ingest.broker.models import BrokerRefused
    from tb.ingest.broker.transport import READ_FIELDS, validate_request

    order_types = {2106, 2107, 2108, 2109, 2110, 2111}  # new/cancel/amend/amendSLTP/close
    assert not order_types & READ_FIELDS.keys()
    for kind in order_types:
        with pytest.raises(BrokerRefused):
            validate_request(kind, {"ctidTraderAccountId": 1})
    with pytest.raises(BrokerRefused):  # smuggled order fields into an allowlisted read
        validate_request(2112, {"ctidTraderAccountId": 1, "volume": 100, "tradeSide": 1})
    with pytest.raises(BrokerRefused):
        validate_request(True, {})  # type: ignore[arg-type]


def test_mt5_python_boundary_exposes_reads_only() -> None:
    from tb.ingest.mt5.adapter import PYTHON_READS
    from tb.ingest.mt5.mcp import MCP_READ_TOOLS

    for name in PYTHON_READS | set(MCP_READ_TOOLS):
        assert not re.search(r"(?i)order|position|trade|close|modify|shell|exec", name), name


def test_requested_ctrader_scope_is_view_only() -> None:
    source = (SRC / "ingest/broker/onboarding/models.py").read_text(encoding="utf-8")
    assert '"scope": "accounts"' in source and '"trading"' not in source


# --------------------------------------------------------------------------- OAuth callback


def test_oauth_callback_session_rejects_non_loopback_and_unsolicited() -> None:
    from tb.ingest.broker.onboarding.models import CallbackSession, OAuthRefused

    for bad in [
        "http://0.0.0.0:8765/ctrader/callback/" + "a" * 43,
        "http://localhost:8765/ctrader/callback/" + "a" * 43,
        "https://127.0.0.1:8765/ctrader/callback/" + "a" * 43,
        "http://127.0.0.1:80/ctrader/callback/" + "a" * 43,
        "http://127.0.0.1:8765/ctrader/callback/short",
        "http://127.0.0.1:8765/ctrader/callback/" + "a" * 43 + "?x=1",
    ]:
        with pytest.raises(OAuthRefused):
            CallbackSession(SecretStr(bad))
    session = CallbackSession.prepare(8765)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(OAuthRefused):  # not armed by the owner
        session.accept("127.0.0.1:8765", session.path + "?code=abc", now)
    session.activate(now)
    for host, target in [
        ("evil.example:8765", session.path + "?code=abc"),
        ("127.0.0.1:8765", "/ctrader/callback/" + "b" * 43 + "?code=abc"),
        ("127.0.0.1:8765", session.path + "?code=abc&state=x"),
        ("127.0.0.1:8765", session.path),
    ]:
        with pytest.raises(OAuthRefused):
            session.accept(host, target, now)
    code = session.accept("127.0.0.1:8765", session.path + "?code=abc", now)
    assert "abc" not in repr(code)
    with pytest.raises(OAuthRefused):  # single use
        session.accept("127.0.0.1:8765", session.path + "?code=abc", now)


def test_oauth_callback_listener_binds_loopback_with_bounded_lifetime() -> None:
    source = (SRC / "ingest/broker/onboarding/callback.py").read_text(encoding="utf-8")
    assert 'LoopbackServer(("127.0.0.1", session.port)' in source
    assert "0.0.0.0" not in source and "log_message" in source
    assert "deadline = time.monotonic() + 300" in source


# --------------------------------------------------------------------------- secret handling


def test_blank_and_missing_keys_disable_every_feature(monkeypatch, tmp_path) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    env = tmp_path / ".env"
    env.write_text("".join(f"{n.upper()}=   \n" for n in Settings.model_fields), encoding="utf-8")
    settings = Settings(_env_file=env)  # type: ignore[call-arg]
    flags = features_enabled(settings)
    assert not any(v for k, v in flags.items() if k != "ollama")
    assert settings.known_secret_values() == ()


def test_settings_repr_and_doctor_do_not_disclose_secrets(monkeypatch, tmp_path) -> None:
    from tb.cli import collect_doctor_report

    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    settings = Settings(_env_file=tmp_path / "missing.env")  # type: ignore[call-arg]
    assert SECRET not in repr(settings) and SECRET not in str(settings.model_dump())
    report = collect_doctor_report(root=tmp_path, settings=settings, gpu_probe=lambda: None)
    assert SECRET not in json.dumps(report, default=str)
    assert report["features"]["openai"] is True and report["network_used"] is False


def test_doctor_runs_end_to_end_with_zero_keys(monkeypatch, tmp_path) -> None:
    from typer.testing import CliRunner

    import tb.cli as cli

    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    zero = Settings(_env_file=tmp_path / "none.env")  # type: ignore[call-arg]
    monkeypatch.setattr(cli, "load_settings", lambda: zero)
    monkeypatch.setattr(cli, "_gpu_name", lambda: None)
    result = CliRunner().invoke(cli.app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "OFF" in result.output


def test_twelve_data_key_travels_only_in_header_never_url(tmp_path) -> None:
    from tb.ingest.twelve_data.client import CreditBudget, TwelveDataClient, TwelveDataSettings

    now = datetime(2026, 10, 23, 18, 0, 5, tzinfo=UTC)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = {
            "plan_limit": 8,
            "plan_daily_limit": 800,
            "current_usage": 0,
            "daily_usage": 0,
            "plan_category": "basic",
        }
        return httpx.Response(200, json=body, headers={"Date": format_datetime(now, usegmt=True)})

    budget = CreditBudget(tmp_path / "c.sqlite", hashlib.sha256(SECRET.encode()).hexdigest())
    client = TwelveDataClient(
        TwelveDataSettings(api_key=SecretStr(SECRET)),
        budget,
        fixture_transport=httpx.MockTransport(handler),
        clock=lambda: now,
    )
    try:
        client.get("api_usage")
    finally:
        client.close()
        budget.close()
    assert seen and all(SECRET not in str(r.url) for r in seen)
    assert seen[0].headers["Authorization"] == "apikey " + SECRET
    assert SECRET.encode() not in (tmp_path / "c.sqlite").read_bytes()


def test_twelve_data_refuses_and_masks_credential_echo(tmp_path) -> None:
    from tb.ingest.mt5.models import FeedUnavailable
    from tb.ingest.twelve_data.client import CreditBudget, TwelveDataClient, TwelveDataSettings

    now = datetime(2026, 10, 23, 18, 0, 5, tzinfo=UTC)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"status": "error", "message": "bad key " + SECRET},
            headers={"Date": format_datetime(now, usegmt=True)},
        )

    budget = CreditBudget(tmp_path / "c.sqlite", hashlib.sha256(SECRET.encode()).hexdigest())
    client = TwelveDataClient(
        TwelveDataSettings(api_key=SecretStr(SECRET)),
        budget,
        fixture_transport=httpx.MockTransport(handler),
        clock=lambda: now,
    )
    with pytest.raises(FeedUnavailable) as caught:
        client.get("api_usage")
    client.close()
    budget.close()
    assert SECRET not in str(caught.value) and SECRET not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert SECRET.encode() not in (tmp_path / "c.sqlite").read_bytes()


@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_llm_provider_errors_never_echo_key_or_body(status) -> None:
    from tb.agents.providers.base import ProviderError
    from tb.agents.providers.http import AnthropicProvider, OpenAICompatibleProvider
    from tb.agents.schemas import ProviderRequest

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="invalid key " + SECRET)

    transport = httpx.MockTransport(handler)
    request = ProviderRequest(prompt="p", json_schema={"type": "object"})
    for provider in (
        OpenAICompatibleProvider(
            name="x",
            model="m",
            base_url="https://example.invalid/v1",
            api_key=SecretStr(SECRET),
            client=httpx.Client(transport=transport),
        ),
        AnthropicProvider(
            model="m", api_key=SecretStr(SECRET), client=httpx.Client(transport=transport)
        ),
    ):
        import tb.agents.providers.base as base

        original = base.time.sleep
        base.time.sleep = lambda s: None
        try:
            with pytest.raises(ProviderError) as caught:
                provider.generate(request)
        finally:
            base.time.sleep = original
        assert SECRET not in str(caught.value)


def test_llm_providers_disabled_without_key() -> None:
    from tb.agents.providers.base import ProviderDisabled
    from tb.agents.providers.http import AnthropicProvider, JevProvider, OpenAICompatibleProvider

    def explode(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network attempted without key")

    client = httpx.Client(transport=httpx.MockTransport(explode))
    for provider in (
        OpenAICompatibleProvider(
            name="x", model="m", base_url="https://e.invalid", api_key=None, client=client
        ),
        AnthropicProvider(model="m", api_key=None, client=client),
        JevProvider(),
    ):
        assert provider.enabled is False
        with pytest.raises(ProviderDisabled):
            provider.generate(None)  # type: ignore[arg-type]


@pytest.mark.xfail(
    strict=True,
    reason="FINDING S-3: LLM provider httpx clients default to "
    "trust_env=True, so HTTP(S)_PROXY/.netrc env can reroute bearer keys "
    "(every other adapter pins trust_env=False)",
)
def test_llm_provider_default_clients_ignore_proxy_environment() -> None:
    from tb.agents.providers.http import AnthropicProvider, OllamaProvider, OpenAICompatibleProvider

    clients = [
        OpenAICompatibleProvider(
            name="x", model="m", base_url="https://e.invalid", api_key=SecretStr(SECRET)
        )._client,
        AnthropicProvider(model="m", api_key=SecretStr(SECRET))._client,
        OllamaProvider(
            model="m", host="http://127.0.0.1:11434", parameter_count_b=1, quantization_bits=4
        )._client,
    ]
    assert all(c.trust_env is False for c in clients)


@pytest.mark.xfail(
    strict=True,
    reason="FINDING S-4: RedactingFilter redacts msg/extras but not "
    "exc_info; JsonFormatter writes raw traceback text containing secrets",
)
def test_log_redaction_covers_exception_tracebacks() -> None:
    from tb.core.logging import JsonFormatter, RedactingFilter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter([SECRET]))
    logger = logging.getLogger("tb.audit.redaction")
    logger.handlers[:] = [handler]
    logger.propagate = False
    try:
        raise RuntimeError(f"upstream rejected api_key={SECRET}")
    except RuntimeError:
        logger.exception("provider call failed")
    assert SECRET not in stream.getvalue()


def test_log_redaction_covers_message_args_and_extras() -> None:
    from tb.core.logging import JsonFormatter, RedactingFilter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter([SECRET]))
    logger = logging.getLogger("tb.audit.redaction2")
    logger.handlers[:] = [handler]
    logger.propagate = False
    logger.info("key %s", SECRET, extra={"api_key": SECRET, "note": f"Bearer {SECRET}"})
    logger.info("header Authorization: Bearer abcdefghijklmnop")
    out = stream.getvalue()
    assert SECRET not in out and "abcdefghijklmnop" not in out


# --------------------------------------------------------------------------- dashboard / scripts


def test_streamlit_binds_loopback_only() -> None:
    config = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    assert re.search(r'(?m)^address\s*=\s*"127\.0\.0\.1"', config)
    launcher = (ROOT / "scripts/run-dashboard.ps1").read_text(encoding="utf-8")
    assert "--server.address 127.0.0.1" in launcher
    for script in (ROOT / "scripts").glob("*.ps1"):
        text = script.read_text(encoding="utf-8")
        assert "0.0.0.0" not in text and "server.address 0" not in text, script.name


def test_dashboard_has_no_network_write_or_order_capability() -> None:
    forbidden = re.compile(
        r"^\s*(import|from)\s+(httpx|requests|urllib|socket|websockets|MetaTrader5|"
        r"tb\.execution|tb\.ingest\.broker\.(transport|ctrader|onboarding)|tb\.ingest\.oanda|"
        r"tb\.ingest\.twelve_data\.client|tb\.agents\.providers)\b",
        re.MULTILINE,
    )
    writes = re.compile(
        r"\.(write_text|write_bytes|to_parquet|write_parquet|unlink)\(|"
        r"open\([^)]*['\"][wa]"
    )
    widgets = re.compile(
        r"st\.(text_input|number_input|slider|data_editor|file_uploader|"
        r"form_submit_button|button)\("
    )
    problems = []
    for path in sorted((SRC / "dashboard").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            problems.append(f"{path.name}: network/execution import")
        if path.name != "fixtures.py" and writes.search(text):
            problems.append(f"{path.name}: file write")
        if widgets.search(text):
            problems.append(f"{path.name}: free-form/mutating widget")
    assert problems == []


def test_powershell_scripts_have_no_remote_code_execution_patterns() -> None:
    bad = re.compile(
        r"(?i)invoke-expression|\biex\b|downloadstring|downloadfile|"
        r"invoke-webrequest|invoke-restmethod|\birm\b|\biwr\b|set-executionpolicy|"
        r"-encodedcommand"
    )
    hits = []
    for script in sorted((ROOT / "scripts").rglob("*.ps1")):
        for number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            if not line.lstrip().startswith("#") and bad.search(line):
                hits.append(f"{script.name}:{number}")
    assert hits == []


def test_src_never_requests_withdrawal_or_puts_keys_in_query_strings() -> None:
    query_secret = re.compile(r"(?i)[?&](api_?key|apikey|token|access_token|secret|signature)=")
    params_secret = re.compile(r"(?i)params\s*=\s*\{[^}]*['\"](api_?key|apikey|token|secret)['\"]")
    hits = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if query_secret.search(text) or params_secret.search(text):
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


@pytest.mark.xfail(
    strict=True,
    reason="FINDING S-6: MLflow telemetry is never disabled; default test "
    "tests/unit/test_ml_tracking.py resolves config.mlflow-telemetry.io (outbound network)",
)
def test_mlflow_telemetry_is_disabled_by_project_code() -> None:
    sources = [p.read_text(encoding="utf-8") for p in sorted(SRC.rglob("*.py"))]
    sources.append((ROOT / "tests" / "conftest.py").read_text(encoding="utf-8"))
    assert any(re.search(r"MLFLOW_DISABLE_TELEMETRY|DO_NOT_TRACK", s) for s in sources)
