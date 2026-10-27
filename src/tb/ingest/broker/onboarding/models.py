"""Secret-safe, bounded OAuth state and distinct pinned cTrader permission enums."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from urllib.parse import parse_qsl, urlencode, urlsplit

from pydantic import SecretStr

from tb.ingest.broker.book import integer


class OAuthRefused(ValueError):
    """Only static local refusal categories may reach the owner or logs."""


class ClientPermissionScope(Enum):
    SCOPE_VIEW = 0
    SCOPE_TRADE = 1


class AccessRights(Enum):
    FULL_ACCESS = 0
    CLOSE_ONLY = 1
    NO_TRADING = 2
    NO_LOGIN = 3


def require_view_scope(value: object) -> ClientPermissionScope:
    """Parse token permissionScope only; account enum objects are never interchangeable."""
    if (type(value) is int and value == 0) or (type(value) is str and value == "SCOPE_VIEW"):
        return ClientPermissionScope.SCOPE_VIEW
    raise OAuthRefused("oauth_returned_token_permission_not_view")


def parse_access_rights(value: object) -> AccessRights:
    """Parse the independently named trader.accessRights field without wire defaults."""
    try:
        if type(value) is int:
            return AccessRights(value)
        if type(value) is str:
            return AccessRights[value]
    except (KeyError, ValueError):
        pass
    raise OAuthRefused("oauth_account_access_rights_missing_or_invalid")


def utc(value: datetime) -> datetime:
    """Refuse naive clocks rather than infer local timezone for authorization state."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise OAuthRefused("oauth_utc_clock_required")
    return value.astimezone(UTC)


def private_value(value: object) -> SecretStr:
    """Bound untrusted token strings without including rejected input in an exception."""
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9._~+/=-]{1,4096}", value):
        raise OAuthRefused("oauth_private_value_invalid")
    return SecretStr(value)


@dataclass(frozen=True, repr=False)
class AppKeys:
    client_id: SecretStr
    client_secret: SecretStr

    def require(self) -> None:
        """Missing application keys disable onboarding; no default credentials exist."""
        private_value(self.client_id.get_secret_value())
        private_value(self.client_secret.get_secret_value())


@dataclass(frozen=True, repr=False)
class TokenPair:
    access: SecretStr
    refresh: SecretStr
    issued_at: datetime
    expires_at: datetime

    @classmethod
    def parse(cls, response: object, now: datetime) -> TokenPair:
        """Use returned seconds, not an assumed thirty-day expiry or provider error text."""
        try:
            if (
                not isinstance(response, dict)
                or response.get("errorCode") is not None
                or response.get("error") is not None
            ):
                raise ValueError
            if str(response.get("tokenType", "")).lower() != "bearer":
                raise ValueError
            seconds = integer(response.get("expiresIn"))
            if not 1 <= seconds <= 2628000:
                raise ValueError
            return cls(
                private_value(response.get("accessToken")),
                private_value(response.get("refreshToken")),
                utc(now),
                utc(now) + timedelta(seconds=seconds),
            )
        except Exception:
            raise OAuthRefused("oauth_token_response_invalid") from None

    def require_current(self, now: datetime) -> None:
        """Expired/reversed token clocks cannot support identity verification."""
        private_value(self.access.get_secret_value())
        private_value(self.refresh.get_secret_value())
        if not self.issued_at <= utc(now) < self.expires_at:
            raise OAuthRefused("oauth_access_token_expired_or_clock_invalid")


@dataclass(repr=False)
class AuthorizationCode:
    value: SecretStr
    received_at: datetime
    redirect: SecretStr
    used: bool = False

    def consume(self, now: datetime) -> str:
        """Keep codes in one-use memory only; conservative local age is not provider issue time."""
        if self.used or not 0 <= (utc(now) - self.received_at).total_seconds() < 45:
            raise OAuthRefused("oauth_authorization_code_expired_or_used")
        self.used = True
        value = private_value(self.value.get_secret_value()).get_secret_value()
        self.value = SecretStr("")
        return value


@dataclass(repr=False)
class CallbackSession:
    redirect: SecretStr
    active_at: datetime | None = None
    used: bool = False
    port: int = field(init=False)
    path: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            text = self.redirect.get_secret_value()
            uri = urlsplit(text)
            if (
                uri.scheme != "http"
                or uri.hostname != "127.0.0.1"
                or uri.port is None
                or not 1024 <= uri.port <= 65535
                or not re.fullmatch(r"/ctrader/callback/[A-Za-z0-9_-]{43}", uri.path)
                or text != f"http://127.0.0.1:{uri.port}{uri.path}"
            ):
                raise ValueError
            self.port, self.path = uri.port, uri.path
        except Exception:
            raise OAuthRefused("oauth_exact_loopback_redirect_required") from None

    @classmethod
    def prepare(cls, port: int = 8765) -> CallbackSession:
        """Owner must register this exact one-use URI before authorization; never wildcard it."""
        return cls(
            SecretStr(f"http://127.0.0.1:{port}/ctrader/callback/{secrets.token_urlsafe(32)}")
        )

    def activate(self, now: datetime) -> None:
        """Only an explicit owner-started session can arm callback acceptance."""
        if self.active_at is not None or self.used:
            raise OAuthRefused("oauth_session_cannot_be_rearmed")
        self.active_at = utc(now)

    def authorization_url(self, keys: AppKeys) -> str:
        """Return a browser-only authorization URI; callers must never print or log it."""
        keys.require()
        return "https://id.ctrader.com/my/settings/openapi/grantingaccess/?" + urlencode(
            {
                "client_id": keys.client_id.get_secret_value(),
                "redirect_uri": self.redirect.get_secret_value(),
                "scope": "accounts",
                "product": "web",
            }
        )

    def accept(self, host: str, target: str, now: datetime) -> AuthorizationCode:
        """Require literal host, exact registered capability path and one bounded query."""
        if (
            self.used
            or self.active_at is None
            or not 0 <= (utc(now) - self.active_at).total_seconds() < 300
        ):
            raise OAuthRefused("oauth_callback_unsolicited_expired_or_reused")
        if len(target) > 8192 or host != f"127.0.0.1:{self.port}":
            raise OAuthRefused("oauth_callback_host_or_size_invalid")
        try:
            path, separator, query = target.partition("?")
            if path != self.path or not separator:
                raise ValueError
            fields = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
            if fields and fields[0][0] == "error" and len(fields) == 1:
                self.used = True
                raise OAuthRefused("oauth_owner_authorization_denied")
            if len(fields) != 1 or fields[0][0] != "code":
                raise ValueError
            code = private_value(fields[0][1])
        except OAuthRefused:
            raise
        except Exception:
            raise OAuthRefused("oauth_callback_fields_or_path_invalid") from None
        self.used = True
        return AuthorizationCode(code, utc(now), self.redirect)
