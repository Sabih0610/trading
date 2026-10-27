"""Owned private state and actual fake-loopback flow; real provider constructors forbidden."""

import dataclasses
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tb.ingest.broker.fixtures import START
from tb.ingest.broker.onboarding.fixtures import owned_channel as channel
from tb.ingest.broker.onboarding.fixtures import owned_keys as keys
from tb.ingest.broker.onboarding.fixtures import owned_rehearsal
from tb.ingest.broker.onboarding.fixtures import owned_token_reply as token_reply
from tb.ingest.broker.onboarding.models import OAuthRefused, TokenPair
from tb.ingest.broker.onboarding.private import PrivateEnv, require_private
from tb.ingest.broker.onboarding.service import FixedTokenEndpoint, NetworkConsent, verify_grant
from tb.ingest.broker.onboarding.workflow import configuration, prepare, save_tokens, stored_tokens

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def env(tmp_path):
    private = PrivateEnv(tmp_path)
    private.update(
        private.read(),
        {
            "CTRADER_DEMO_CLIENT_ID": "owned-client",
            "CTRADER_DEMO_CLIENT_SECRET": "owned-app-secret",
            "CTRADER_DEMO_ACCOUNT_ID": "777",
            "CTRADER_DEMO_BROKER_PIN": "Owned protocol fixture",
        },
    )
    return private


def test_owned_fake_local_provider_callback_grant_and_acl_never_construct_real_clients(
    tmp_path, monkeypatch, capsys, caplog
):
    def forbidden(*args, **kwargs):
        raise AssertionError("genuine provider constructor reached")

    monkeypatch.setattr("http.client.HTTPSConnection", forbidden)
    monkeypatch.setattr("tb.ingest.broker.onboarding.cli.DemoJsonChannel", forbidden)
    with caplog.at_level(logging.DEBUG):
        report = owned_rehearsal(tmp_path)
    assert (
        report["genuine_provider_calls"]
        == report["external_orders"]
        == report["quotes_collected"]
        == 0
    )
    assert report["fake_loopback_token_requests"] == 1
    require_private(tmp_path / ".env")
    output = capsys.readouterr()
    for text in [output.out, output.err, caplog.text, json.dumps(report)]:
        assert not any(
            v in text
            for v in [
                "owned-app-secret",
                "owned-access",
                "owned-refresh",
                "owned-code",
                "777",
                "/ctrader/callback/",
            ]
        )
    files = [p for p in tmp_path.rglob("*") if p.is_file() and p.name != ".env"]
    assert not any(
        b"owned-access" in p.read_bytes() or b"owned-app-secret" in p.read_bytes() for p in files
    )


@pytest.mark.parametrize("phase", ["before_replace", "after_replace"])
def test_interrupted_private_token_pair_is_old_or_new_never_mixed(env, phase):
    env.update(
        env.read(),
        {
            "CTRADER_DEMO_ACCESS_TOKEN": "owned-old-access",
            "CTRADER_DEMO_REFRESH_TOKEN": "owned-old-refresh",
        },
    )

    def crash(at):
        if at == phase:
            raise OSError("owned-secret-injected-error")

    with pytest.raises(OAuthRefused) as error:
        env.update(
            env.read(),
            {
                "CTRADER_DEMO_ACCESS_TOKEN": "owned-new-access",
                "CTRADER_DEMO_REFRESH_TOKEN": "owned-new-refresh",
            },
            fault=crash,
        )
    current = env.read().values
    prefix = "owned-old" if phase == "before_replace" else "owned-new"
    assert current["CTRADER_DEMO_ACCESS_TOKEN"] == prefix + "-access"
    assert current["CTRADER_DEMO_REFRESH_TOKEN"] == prefix + "-refresh"
    assert not list(env.root.glob(".env.*"))
    assert "owned-secret" not in str(error.value) and error.value.__suppress_context__


@pytest.mark.parametrize(
    "bad",
    [
        'CTRADER_DEMO_ACCESS_TOKEN="unfinished',
        "CTRADER_DEMO_CLIENT_ID=a\nCTRADER_DEMO_CLIENT_ID=b",
        "not an assignment",
    ],
)
def test_malformed_private_state_refuses_without_repair(env, bad):
    env.path.write_text(bad, encoding="utf-8")
    before = env.path.read_bytes()
    with pytest.raises(OAuthRefused):
        env.read()
    assert env.path.read_bytes() == before


def test_weak_existing_permissions_are_refused_and_not_silently_changed(tmp_path):
    path = tmp_path / ".env"
    path.write_text("CTRADER_DEMO_CLIENT_ID=owned-client\n")
    if os.name != "nt":
        path.chmod(0o644)
    with pytest.raises(OAuthRefused):
        PrivateEnv(tmp_path).read()


def test_optimistic_writer_version_cannot_overwrite_another_update(env):
    first = env.read()
    env.update(first, {"CTRADER_DEMO_TOKEN_TYPE": "bearer"})
    with pytest.raises(OAuthRefused):
        env.update(first, {"CTRADER_DEMO_TOKEN_TYPE": "stale"})
    assert env.read().values["CTRADER_DEMO_TOKEN_TYPE"] == "bearer"


def test_complete_verification_proof_is_required_to_commit_tokens(env):
    tokens = TokenPair.parse(token_reply(), START)
    proof = verify_grant(channel(), keys(), tokens, "777", "Owned protocol fixture", START)
    for changed in [
        dataclasses.replace(proof, account="999"),
        dataclasses.replace(proof, server="other.invalid"),
        dataclasses.replace(proof, access_binding="wrong"),
    ]:
        with pytest.raises(OAuthRefused):
            save_tokens(env, tokens, changed, START)
    assert "CTRADER_DEMO_ACCESS_TOKEN" not in env.read().values
    save_tokens(env, tokens, proof, START)
    assert stored_tokens(env.read()) == tokens
    v = env.read().values
    assert v["CTRADER_DEMO_TOKEN_PERMISSION"] == "SCOPE_VIEW"
    assert v["CTRADER_DEMO_ACCOUNT_ACCESS_RIGHTS"] == "FULL_ACCESS"
    assert v["CTRADER_DEMO_OAUTH_CALLBACK_STATE"] == "consumed"
    assert not any("code" in name.lower() for name in v)
    for name, value in [
        ("CTRADER_DEMO_ACCOUNT_ID", "999"),
        ("CTRADER_DEMO_CLIENT_ID", "owned-other-app"),
        ("CTRADER_DEMO_BROKER_PIN", "Other"),
    ]:
        snapshot = env.read()
        invalid = dataclasses.replace(snapshot, values={**snapshot.values, name: value})
        with pytest.raises(OAuthRefused):
            configuration(invalid)


def test_preparation_rotates_private_uri_but_never_opens_browser_or_provider(env, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider/browser reached")

    monkeypatch.setattr("webbrowser.open", forbidden)
    monkeypatch.setattr("http.client.HTTPSConnection", forbidden)
    prepare(env)
    first = env.read()
    prepare(env)
    second = env.read()
    assert (
        first.values["CTRADER_DEMO_OAUTH_REDIRECT_URI"]
        != second.values["CTRADER_DEMO_OAUTH_REDIRECT_URI"]
    )
    assert second.values["CTRADER_DEMO_OAUTH_CALLBACK_STATE"] == "prepared"
    assert second.values["CTRADER_DEMO_CLIENT_SECRET"] == "owned-app-secret"


def test_default_genuine_boundary_and_ci_even_explicit_consent_are_disabled(monkeypatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    for consent in [NetworkConsent(), NetworkConsent(True, True, True)]:
        with pytest.raises(OAuthRefused):
            FixedTokenEndpoint(consent)


def test_default_cli_missing_keys_is_inert_and_has_no_sensitive_fields():
    result = subprocess.run(
        [sys.executable, "-m", "tb.ingest.broker.onboarding.cli"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["configured"] is False and report["external_orders_enabled"] is False
    assert report["genuine_connectivity"] == "UNVERIFIED"


def test_failed_owner_auth_cannot_construct_provider(env, monkeypatch):
    from tb.ingest.broker.onboarding.cli import authorize

    def forbidden(*args, **kwargs):
        raise AssertionError("provider reached")

    monkeypatch.setattr("tb.ingest.broker.onboarding.cli.DemoJsonChannel", forbidden)
    monkeypatch.setattr("http.client.HTTPSConnection", forbidden)
    for explicit in (False, True):
        with pytest.raises(OAuthRefused):
            authorize(env, after_approval=explicit)


def test_owned_env_is_git_ignored_and_example_values_are_empty(env):
    require_private(env.path)
    names = [
        line
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line.startswith("CTRADER_DEMO_")
    ]
    assert names and all(line.partition("=")[2] == "" for line in names)


def test_preparation_cannot_replace_a_callback_during_another_owner_session(env):
    before = env.read().sha256
    with env.session_lease():
        with pytest.raises(OAuthRefused, match="session_already_active"):
            prepare(env)
    assert env.read().sha256 == before


@pytest.mark.parametrize("confirm", [True, False])
def test_future_owner_coordinator_is_rehearsed_only_with_all_provider_edges_mocked(
    env, monkeypatch, confirm
):
    from tb.ingest.broker.onboarding.cli import authorize

    monkeypatch.delenv("TB_OFFLINE_VALIDATION", raising=False)
    env.update(
        env.read(),
        {"CTRADER_DEMO_APPLICATION_APPROVED": "true", "CTRADER_DEMO_OAUTH_ENABLED": "true"},
    )
    prepare(env)
    requests, channels, browsers = [], [], []

    class Wire:
        def request(self, fields):
            requests.append(fields["grant_type"])
            return token_reply("two" if fields["grant_type"] == "refresh_token" else "one")

    def fake_receive(session, clock, ready):
        ready()
        return session.accept("127.0.0.1:8765", session.path + "?code=owned-code", clock())

    def new_channel():
        wire = channel()
        channels.append(wire)
        return wire

    monkeypatch.setattr("tb.ingest.broker.onboarding.cli.FixedTokenEndpoint", lambda _: Wire())
    monkeypatch.setattr("tb.ingest.broker.onboarding.cli.DemoJsonChannel", new_channel)
    monkeypatch.setattr("tb.ingest.broker.onboarding.cli.receive_callback", fake_receive)
    monkeypatch.setattr(
        "webbrowser.open", lambda *args, **kwargs: browsers.append("owned_browser") or True
    )
    monkeypatch.setattr("getpass.getpass", lambda _: "777" if confirm else "999")
    if not confirm:
        with pytest.raises(OAuthRefused, match="confirmation_refused"):
            authorize(env, after_approval=True)
        assert "CTRADER_DEMO_ACCESS_TOKEN" not in env.read().values
    else:
        authorize(env, after_approval=True)
        with pytest.raises(OAuthRefused, match="new_callback_first"):
            authorize(env, after_approval=True)
        assert requests == ["authorization_code"]
        authorize(env, after_approval=True, refresh=True)
        assert env.read().values["CTRADER_DEMO_ACCESS_TOKEN"] == "owned-access-two"
        assert requests == ["authorization_code", "refresh_token"]
    assert all(wire.closed and wire.calls == [2100, 2149, 2102, 2121] for wire in channels)
    assert browsers == ["owned_browser"]
