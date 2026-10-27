"""Narrow token exchange and one-account verification; no quote or order orchestration."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import ssl
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import urlencode

from pydantic import SecretStr

from tb.ingest.broker.book import integer
from tb.ingest.broker.models import SERVER
from tb.ingest.broker.onboarding.models import (
    AccessRights,
    AppKeys,
    AuthorizationCode,
    CallbackSession,
    ClientPermissionScope,
    OAuthRefused,
    TokenPair,
    parse_access_rights,
    require_view_scope,
    utc,
)
from tb.ingest.broker.transport import ReadChannel


@dataclass(frozen=True)
class NetworkConsent:
    application_approved: bool = False
    owner_enabled: bool = False
    explicit_invocation: bool = False

    def require(self) -> None:
        """Default-deny at every real transport boundary; CI can never authorize a provider."""
        if (
            self.application_approved is not True
            or self.owner_enabled is not True
            or self.explicit_invocation is not True
            or os.environ.get("TB_OFFLINE_VALIDATION") == "1"
        ):
            raise OAuthRefused("oauth_genuine_network_not_authorized")


class TokenWire(Protocol):
    def request(self, fields: dict[str, str]) -> object: ...


class FixedTokenEndpoint:
    """HTTPS only, no proxies/redirects/debug/logger, bounded body and fixed host/path.

    Query secrets exist in memory/wire because that is the documented provider protocol.
    No full request URI is ever returned, printed, passed to a browser or wrapped in an error.
    """

    def __init__(self, consent: NetworkConsent) -> None:
        consent.require()
        self.consent = consent

    def request(self, fields: dict[str, str]) -> object:
        self.consent.require()
        expected = {"grant_type", "client_id", "client_secret"}
        if fields.get("grant_type") == "authorization_code":
            expected |= {"code", "redirect_uri"}
            CallbackSession(SecretStr(fields.get("redirect_uri", "")))
        elif fields.get("grant_type") == "refresh_token":
            expected.add("refresh_token")
        else:
            raise OAuthRefused("oauth_token_grant_not_supported")
        if set(fields) != expected or any(
            type(v) is not str or not 1 <= len(v) <= 8192 for v in fields.values()
        ):
            raise OAuthRefused("oauth_token_fields_invalid")
        connection = http.client.HTTPSConnection(
            "openapi.ctrader.com", 443, timeout=10, context=ssl.create_default_context()
        )
        try:
            connection.set_debuglevel(0)
            connection.request(
                "GET", "/apps/token?" + urlencode(fields), headers={"Accept": "application/json"}
            )
            response = connection.getresponse()
            body = response.read(16385)
            if (
                response.status != 200
                or len(body) > 16384
                or response.getheader("Content-Type", "").split(";")[0].strip()
                != "application/json"
            ):
                raise ValueError
            return json.loads(body)
        except Exception:
            raise OAuthRefused("oauth_https_token_request_refused") from None
        finally:
            connection.close()


class TokenService:
    """Injected owned wire in tests; real wire requires separate explicit owner consent."""

    def __init__(self, wire: TokenWire, keys: AppKeys) -> None:
        keys.require()
        self.wire, self.keys = wire, keys

    def _request(self, values: dict[str, str], now: datetime) -> TokenPair:
        try:
            return TokenPair.parse(
                self.wire.request(
                    {
                        "client_id": self.keys.client_id.get_secret_value(),
                        "client_secret": self.keys.client_secret.get_secret_value(),
                        **values,
                    }
                ),
                now,
            )
        except Exception:
            raise OAuthRefused("oauth_token_exchange_refused") from None

    def exchange(
        self, code: AuthorizationCode, session: CallbackSession, now: datetime
    ) -> TokenPair:
        """Redeem once immediately after a matched callback; no code is saved to disk."""
        if (
            session.active_at is None
            or not session.used
            or code.redirect != session.redirect
            or not 0 <= (utc(now) - session.active_at).total_seconds() < 300
        ):
            raise OAuthRefused("oauth_code_redirect_binding_refused")
        return self._request(
            {
                "grant_type": "authorization_code",
                "code": code.consume(now),
                "redirect_uri": session.redirect.get_secret_value(),
            },
            now,
        )

    def refresh(self, previous: TokenPair, now: datetime) -> TokenPair:
        """Explicit manual operation only; no timer, retry loop or automatic refresh exists."""
        if utc(now) < previous.issued_at:
            raise OAuthRefused("oauth_refresh_clock_invalid")
        fresh = self._request(
            {"grant_type": "refresh_token", "refresh_token": previous.refresh.get_secret_value()},
            now,
        )
        if fresh.access == previous.access or fresh.refresh == previous.refresh:
            raise OAuthRefused("oauth_token_rotation_not_confirmed")
        return fresh


def binding(value: str) -> str:
    """Private binding digest, never a public authorization or performance artifact."""
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True, repr=False)
class VerifiedGrant:
    account: str
    broker: str
    server: str
    scope: ClientPermissionScope
    access_rights: AccessRights
    checked_at: datetime
    access_binding: str
    application_binding: str

    @property
    def fingerprint(self) -> str:
        return binding(f"{self.server}:{self.account}")


def verify_grant(
    channel: ReadChannel,
    keys: AppKeys,
    tokens: TokenPair,
    account: str,
    broker: str,
    now: datetime,
    *,
    server: str = SERVER,
) -> VerifiedGrant:
    """Authenticate no more than one independently pinned demo account, then close the channel."""
    try:
        keys.require()
        tokens.require_current(now)
        if server != SERVER or str(integer(account)) != account or not 1 <= len(broker) <= 100:
            raise ValueError
        channel.request(
            2100,
            {
                "clientId": keys.client_id.get_secret_value(),
                "clientSecret": keys.client_secret.get_secret_value(),
            },
        )
        token = tokens.access.get_secret_value()
        listing = channel.request(2149, {"accessToken": token})
        if listing.get("accessToken") != token:
            raise ValueError
        scope = require_view_scope(listing.get("permissionScope"))
        rows = listing.get("ctidTraderAccount")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError
        row: dict[str, Any] = rows[0]
        if (
            integer(row.get("ctidTraderAccountId")) != int(account)
            or row.get("isLive") is not False
            or row.get("brokerTitleShort") != broker
        ):
            raise ValueError
        auth = channel.request(2102, {"ctidTraderAccountId": int(account), "accessToken": token})
        if integer(auth.get("ctidTraderAccountId")) != int(account):
            raise ValueError
        response = channel.request(2121, {"ctidTraderAccountId": int(account)})
        trader = response.get("trader")
        if (
            integer(response.get("ctidTraderAccountId")) != int(account)
            or not isinstance(trader, dict)
            or integer(trader.get("ctidTraderAccountId")) != int(account)
        ):
            raise ValueError
        rights = parse_access_rights(trader.get("accessRights"))
        if rights is AccessRights.NO_LOGIN:
            raise ValueError
        return VerifiedGrant(
            account,
            broker,
            server,
            scope,
            rights,
            utc(now),
            binding(token),
            binding(keys.client_id.get_secret_value()),
        )
    except Exception:
        raise OAuthRefused("oauth_demo_grant_verification_refused") from None
    finally:
        try:
            channel.close()
        except Exception:
            raise OAuthRefused("oauth_channel_close_refused") from None
