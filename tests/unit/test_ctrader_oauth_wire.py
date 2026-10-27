"""Fixed HTTPS shape through an in-memory connection; no genuine request is made."""

import ast
import json
from pathlib import Path

import pytest

from tb.ingest.broker.onboarding.models import CallbackSession, OAuthRefused
from tb.ingest.broker.onboarding.private import PrivateSnapshot
from tb.ingest.broker.onboarding.service import FixedTokenEndpoint, NetworkConsent
from tb.ingest.broker.onboarding.workflow import stored_tokens


@pytest.mark.parametrize("failure", [None, "redirect", "timeout", "large", "type", "json"])
def test_https_fixed_bounded_without_redirects_or_credential_logs(
    monkeypatch, caplog, capsys, failure
):
    calls = []

    class Response:
        status = 302 if failure == "redirect" else 200

        def getheader(self, name, default):
            return "text/html" if failure == "type" else "application/json"

        def read(self, limit):
            assert limit == 16385
            if failure == "large":
                return b"x" * 16385
            if failure == "json":
                return b"invalid owned-secret-body"
            return json.dumps({"owned_fixture": True}).encode()

    class Connection:
        def __init__(self, host, port, **kwargs):
            assert (host, port, kwargs["timeout"]) == ("openapi.ctrader.com", 443, 10)

        def set_debuglevel(self, level):
            assert level == 0

        def request(self, method, target, **kwargs):
            calls.append(method)
            assert target.startswith("/apps/token?")
            if failure == "timeout":
                raise TimeoutError(target)

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.delenv("TB_OFFLINE_VALIDATION", raising=False)
    monkeypatch.setattr("http.client.HTTPSConnection", Connection)
    endpoint = FixedTokenEndpoint(NetworkConsent(True, True, True))
    fields = {
        "grant_type": "authorization_code",
        "client_id": "owned-client",
        "client_secret": "owned-secret",
        "code": "owned-code",
        "redirect_uri": CallbackSession.prepare().redirect.get_secret_value(),
    }
    if failure:
        with pytest.raises(OAuthRefused) as error:
            endpoint.request(fields)
        assert str(error.value) == "oauth_https_token_request_refused"
    else:
        assert endpoint.request(fields) == {"owned_fixture": True}
    assert calls == ["GET"]
    output = capsys.readouterr()
    assert not any(
        s in caplog.text + output.out + output.err
        for s in ["owned-secret", "owned-code", "/apps/token?"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("CTRADER_DEMO_ACCESS_TOKEN", ""),
        ("CTRADER_DEMO_REFRESH_TOKEN", ""),
        ("CTRADER_DEMO_TOKEN_ISSUED_AT", "invalid"),
        ("CTRADER_DEMO_TOKEN_PERMISSION", "SCOPE_TRADE"),
    ],
)
def test_invalid_persistent_token_state_has_no_secret_error_details(field, value):
    state = {
        "CTRADER_DEMO_ACCESS_TOKEN": "owned-access",
        "CTRADER_DEMO_REFRESH_TOKEN": "owned-refresh",
        "CTRADER_DEMO_TOKEN_ISSUED_AT": "2024-01-08T12:00:00+00:00",
        "CTRADER_DEMO_ACCESS_EXPIRES_AT": "2024-01-08T13:00:00+00:00",
        "CTRADER_DEMO_TOKEN_TYPE": "bearer",
        "CTRADER_DEMO_TOKEN_PERMISSION": "SCOPE_VIEW",
        field: value,
    }
    with pytest.raises(OAuthRefused) as error:
        stored_tokens(PrivateSnapshot(state, "owned", ()))
    assert str(error.value) == "oauth_stored_token_state_invalid"


def test_onboarding_adds_only_four_existing_protocol_messages_without_execution_imports():
    root = Path(__file__).resolve().parents[2] / "src/tb/ingest/broker/onboarding"
    kinds = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(
                    part in (node.module or "").split(".") for part in ["paper", "execution"]
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "request"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and type(node.args[0].value) is int
            ):
                kinds.add(node.args[0].value)
    assert kinds == {2100, 2149, 2102, 2121}
