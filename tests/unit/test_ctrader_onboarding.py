"""Owned OAuth/protocol fixtures only; never use application or account credentials."""

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr

from tb.ingest.broker.fixtures import START, responder
from tb.ingest.broker.onboarding.models import (
    AccessRights,
    AppKeys,
    CallbackSession,
    OAuthRefused,
    TokenPair,
    parse_access_rights,
    require_view_scope,
)
from tb.ingest.broker.onboarding.service import TokenService, verify_grant
from tb.ingest.broker.transport import MockReadChannel


def keys():
    return AppKeys(SecretStr("owned-client"), SecretStr("owned-app-secret"))


def token_reply(suffix="one"):
    return {
        "accessToken": "owned-access-" + suffix,
        "refreshToken": "owned-refresh-" + suffix,
        "tokenType": "bearer",
        "expiresIn": 2628000,
    }


def channel(change=None):
    def answer(kind, payload):
        row = responder(kind, payload)
        if kind == 2121:
            row["trader"]["accessRights"] = 0
        if change:
            change(kind, row)
        return row

    return MockReadChannel(answer, [])


@pytest.mark.parametrize("scope", [0, "SCOPE_VIEW"])
@pytest.mark.parametrize("rights", [0, 1, 2, "FULL_ACCESS", "NO_TRADING"])
def test_token_view_is_independent_of_account_access_rights(scope, rights):
    def change(kind, row):
        if kind == 2149:
            row["permissionScope"] = scope
        if kind == 2121:
            row["trader"]["accessRights"] = rights

    wire = channel(change)
    proof = verify_grant(
        wire, keys(), TokenPair.parse(token_reply(), START), "777", "Owned protocol fixture", START
    )
    assert proof.scope.name == "SCOPE_VIEW"
    assert wire.calls == [2100, 2149, 2102, 2121] and wire.closed


@pytest.mark.parametrize(
    "value", [None, True, False, 1, 2, "0", "SCOPE_TRADE", "FULL_ACCESS", AccessRights.FULL_ACCESS]
)
def test_wrong_enum_or_missing_token_scope_cannot_be_view_permission(value):
    with pytest.raises(OAuthRefused):
        require_view_scope(value)


@pytest.mark.parametrize("value", [None, True, False, "SCOPE_VIEW", "0", -1, 4])
def test_unknown_account_rights_cannot_substitute_for_token_scope(value):
    with pytest.raises(OAuthRefused):
        parse_access_rights(value)


@pytest.mark.parametrize(
    "case",
    [
        "scope_missing",
        "trade",
        "account",
        "broker",
        "extra",
        "live",
        "missing_live",
        "rights",
        "revoked",
        "binding",
    ],
)
def test_verification_refuses_changed_or_ambiguous_grants(case):
    def change(kind, row):
        if kind == 2149:
            if case == "scope_missing":
                row.pop("permissionScope")
            if case == "trade":
                row["permissionScope"] = 1
            if case == "extra":
                row["ctidTraderAccount"] *= 2
            if case == "binding":
                row["accessToken"] = "owned-other-token"
            for flag, name, value in [
                ("account", "ctidTraderAccountId", 999),
                ("broker", "brokerTitleShort", "Other"),
                ("live", "isLive", True),
            ]:
                if case == flag:
                    row["ctidTraderAccount"][0][name] = value
            if case == "missing_live":
                row["ctidTraderAccount"][0].pop("isLive")
        if kind == 2121 and case in {"rights", "revoked"}:
            row["trader"]["accessRights"] = None if case == "rights" else 3

    wire = channel(change)
    with pytest.raises(OAuthRefused):
        verify_grant(
            wire,
            keys(),
            TokenPair.parse(token_reply(), START),
            "777",
            "Owned protocol fixture",
            START,
        )
    assert wire.closed
    assert set(wire.calls) <= {2100, 2149, 2102, 2121}


def test_unexpected_server_and_expired_tokens_refuse_before_protocol_calls():
    for kwargs, at in [({"server": "unexpected.invalid"}, START), ({}, START + timedelta(days=40))]:
        wire = channel()
        with pytest.raises(OAuthRefused):
            verify_grant(
                wire,
                keys(),
                TokenPair.parse(token_reply(), START),
                "777",
                "Owned protocol fixture",
                at,
                **kwargs,
            )
        assert wire.calls == [] and wire.closed


def test_callback_requires_active_one_use_exact_registered_nonce():
    session = CallbackSession.prepare()
    path = urlsplit(session.redirect.get_secret_value()).path
    host = "127.0.0.1:8765"
    with pytest.raises(OAuthRefused):
        session.accept(host, path + "?code=owned-code", START)
    session.activate(START)
    for target in [
        "/callback?code=owned-code",
        path + "?code=a&code=b",
        path + "?code=a&state=x",
        path + "?code=",
        path + "?scope=accounts",
    ]:
        with pytest.raises(OAuthRefused):
            session.accept(host, target, START)
    with pytest.raises(OAuthRefused):
        session.accept("localhost:8765", path + "?code=owned-code", START)
    code = session.accept(host, path + "?code=owned-code", START)
    assert "owned-code" not in repr(code) and path not in repr(session)
    assert code.consume(START) == "owned-code"
    with pytest.raises(OAuthRefused):
        code.consume(START)
    with pytest.raises(OAuthRefused):
        session.accept(host, path + "?code=owned-code", START)


@pytest.mark.parametrize(
    "uri",
    [
        "http://0.0.0.0:8765/callback",
        "http://localhost:8765/callback",
        "https://example.com/callback",
        "http://user@127.0.0.1:8765/callback",
        "http://127.0.0.1:8765/callback?x=1",
    ],
)
def test_only_exact_private_prepared_loopback_uri_is_accepted(uri):
    with pytest.raises(OAuthRefused):
        CallbackSession(SecretStr(uri))


def test_callback_timeout_denial_and_local_code_expiry():
    s = CallbackSession.prepare()
    s.activate(START)
    path = urlsplit(s.redirect.get_secret_value()).path
    with pytest.raises(OAuthRefused):
        s.accept("127.0.0.1:8765", path + "?code=owned-code", START + timedelta(minutes=6))
    s = CallbackSession.prepare()
    s.activate(START)
    path = urlsplit(s.redirect.get_secret_value()).path
    with pytest.raises(OAuthRefused):
        s.accept("127.0.0.1:8765", path + "?error=access_denied", START)
    assert s.used
    s = CallbackSession.prepare()
    s.activate(START)
    code = s.accept(
        "127.0.0.1:8765", urlsplit(s.redirect.get_secret_value()).path + "?code=owned-code", START
    )
    with pytest.raises(OAuthRefused):
        code.consume(START + timedelta(seconds=45))


def test_authorization_has_accounts_only_and_no_undocumented_parameters():
    s = CallbackSession.prepare()
    params = parse_qs(urlsplit(s.authorization_url(keys())).query)
    assert set(params) == {"client_id", "redirect_uri", "scope", "product"}
    assert params["scope"] == ["accounts"] and params["redirect_uri"] == [
        s.redirect.get_secret_value()
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("accessToken", ""),
        ("refreshToken", None),
        ("tokenType", "other"),
        ("expiresIn", 0),
        ("expiresIn", True),
        ("expiresIn", 999999999),
        ("errorCode", "OWNED_ERROR"),
    ],
)
def test_invalid_token_response_is_sanitized(field, value):
    response = {**token_reply(), field: value}
    with pytest.raises(OAuthRefused) as error:
        TokenPair.parse(response, START)
    assert "owned-access" not in str(error.value) and "OWNED_ERROR" not in str(error.value)


def test_manual_rotation_is_atomic_pair_and_uses_only_refresh_grant():
    class Wire:
        def request(self, fields):
            assert fields["grant_type"] == "refresh_token"
            assert set(fields) == {"grant_type", "client_id", "client_secret", "refresh_token"}
            return token_reply("two")

    old = TokenPair.parse(token_reply(), START)
    fresh = TokenService(Wire(), keys()).refresh(old, START + timedelta(days=40))
    assert fresh.access != old.access and fresh.refresh != old.refresh


def test_endpoint_exceptions_never_expose_secret_or_url():
    class Wire:
        def request(self, _fields):
            raise RuntimeError(
                "https://example.invalid/?client_secret=owned-app-secret&code=owned-code"
            )

    s = CallbackSession.prepare()
    s.activate(START)
    code = s.accept(
        "127.0.0.1:8765", urlsplit(s.redirect.get_secret_value()).path + "?code=owned-code", START
    )
    with pytest.raises(OAuthRefused) as error:
        TokenService(Wire(), keys()).exchange(code, s, START)
    assert str(error.value) == "oauth_token_exchange_refused" and error.value.__suppress_context__


def test_code_from_another_callback_is_refused_before_token_wire():
    first, second = CallbackSession.prepare(), CallbackSession.prepare()
    first.activate(START)
    second.activate(START)
    code = first.accept("127.0.0.1:8765", first.path + "?code=owned-code", START)
    calls = []

    class Wire:
        def request(self, fields):
            calls.append(fields["grant_type"])
            return token_reply()

    with pytest.raises(OAuthRefused):
        TokenService(Wire(), keys()).exchange(code, second, START)
    assert calls == []
