"""Explicit fake loopback provider for owned onboarding rehearsal; never a configurable endpoint."""

from __future__ import annotations

import http.client
import json
import socket
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pydantic import SecretStr

from tb.ingest.broker.fixtures import responder
from tb.ingest.broker.onboarding.callback import receive_callback
from tb.ingest.broker.onboarding.models import AppKeys, CallbackSession, OAuthRefused
from tb.ingest.broker.onboarding.private import PrivateEnv, require_private
from tb.ingest.broker.onboarding.service import TokenService, verify_grant
from tb.ingest.broker.onboarding.workflow import configuration, save_tokens
from tb.ingest.broker.transport import MockReadChannel


def owned_keys() -> AppKeys:
    """Explicitly fictional application credentials, never a root .env lookup."""
    return AppKeys(SecretStr("owned-client"), SecretStr("owned-app-secret"))


def owned_token_reply(suffix: str = "one") -> dict[str, str | int]:
    """Fictional token fields for malformed/rotation tests."""
    return {
        "accessToken": "owned-access-" + suffix,
        "refreshToken": "owned-refresh-" + suffix,
        "tokenType": "bearer",
        "expiresIn": 2628000,
    }


def owned_channel(
    change: Callable[[int, dict[str, object]], None] | None = None,
) -> MockReadChannel:
    """Reuse the existing fixed read responder with an explicit owned accessRights fact."""

    def answer(kind: int, payload: dict[str, object]) -> dict[str, object]:
        row = responder(kind, payload)
        if kind == 2121:
            row["trader"]["accessRights"] = 0
        if change:
            change(kind, row)
        return row

    return MockReadChannel(answer, [])


def owned_rehearsal(root: Path) -> dict[str, str | bool | int]:
    """Only generated owned credentials in a fresh disposable root; no production .env read."""
    if (root / ".env").exists():
        raise OAuthRefused("oauth_owned_rehearsal_requires_empty_root")
    env = PrivateEnv(root)
    env.update(
        env.read(),
        {
            "CTRADER_DEMO_CLIENT_ID": "owned-client",
            "CTRADER_DEMO_CLIENT_SECRET": "owned-app-secret",
            "CTRADER_DEMO_ACCOUNT_ID": "777",
            "CTRADER_DEMO_BROKER_PIN": "Owned protocol fixture",
        },
    )
    keys, account, broker, _ = configuration(env.read())
    requests: list[str] = []

    class FakeProvider(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            uri = urlsplit(self.path)
            fields = parse_qs(uri.query)
            valid = (
                uri.path == "/apps/token"
                and fields.get("grant_type") == ["authorization_code"]
                and fields.get("client_id") == ["owned-client"]
                and fields.get("client_secret") == ["owned-app-secret"]
                and fields.get("code") == ["owned-code"]
                and set(fields)
                == {"grant_type", "client_id", "client_secret", "code", "redirect_uri"}
            )
            requests.append("owned_token_request" if valid else "owned_invalid_request")
            body = json.dumps(
                {
                    "accessToken": "owned-access",
                    "refreshToken": "owned-refresh",
                    "expiresIn": 3600,
                    "tokenType": "bearer",
                }
            ).encode()
            self.send_response(200 if valid else 400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer(("127.0.0.1", 0), FakeProvider) as provider:
        thread = threading.Thread(target=provider.serve_forever, daemon=True)
        thread.start()

        class FakeWire:
            def request(self, fields: dict[str, str]) -> object:
                from urllib.parse import urlencode

                connection = http.client.HTTPConnection(
                    "127.0.0.1", provider.server_port, timeout=5
                )
                try:
                    connection.request("GET", "/apps/token?" + urlencode(fields))
                    response = connection.getresponse()
                    if response.status != 200:
                        raise OAuthRefused("owned_fake_provider_refused")
                    return json.loads(response.read(16384))
                finally:
                    connection.close()

        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            session = CallbackSession.prepare(port)
            session.activate(datetime.now(UTC))

            def send_owned_callback() -> None:
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                try:
                    connection.request("GET", session.path + "?code=owned-code")
                    response = connection.getresponse()
                    body = response.read()
                    if response.status != 200 or b"owned-code" in body:
                        raise OAuthRefused("owned_callback_refused_or_reflected")
                finally:
                    connection.close()

            senders: list[threading.Thread] = []

            def ready() -> None:
                sender = threading.Thread(target=send_owned_callback)
                senders.append(sender)
                sender.start()

            code = receive_callback(session, lambda: datetime.now(UTC), ready)
            for sender in senders:
                sender.join(timeout=5)
            tokens = TokenService(FakeWire(), keys).exchange(code, session, datetime.now(UTC))

            def owned_reply(kind: int, payload: dict[str, object]) -> dict[str, object]:
                row = responder(kind, payload)
                if kind == 2121:
                    row["trader"]["accessRights"] = 0
                return row

            channel = MockReadChannel(owned_reply, [])
            proof = verify_grant(channel, keys, tokens, account, broker, datetime.now(UTC))
            save_tokens(env, tokens, proof, datetime.now(UTC))
            require_private(env.path)
            assert requests == ["owned_token_request"] and channel.calls == [2100, 2149, 2102, 2121]
            return {
                "mode": "OWNED OFFLINE OAUTH REHEARSAL",
                "fake_loopback_token_requests": 1,
                "permission_view_verified": True,
                "account_enum_separate": True,
                "private_atomic_storage": True,
                "genuine_provider_calls": 0,
                "quotes_collected": 0,
                "external_orders": 0,
            }
        finally:
            provider.shutdown()
            thread.join(timeout=5)
