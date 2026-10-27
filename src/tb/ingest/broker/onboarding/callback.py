"""Bounded loopback callback listener; no request logging, reflected values or public bind."""

from __future__ import annotations

import base64
import hashlib
import socket
import time
from collections.abc import Callable
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from tb.ingest.broker.onboarding.models import AuthorizationCode, CallbackSession, OAuthRefused

SCRIPT = "history.replaceState(null, '', '/complete');"
BODY = f"<!doctype html><meta charset=utf-8><title>Local authorization</title><script>{SCRIPT}</script><p>Return to the local helper. Do not share this page or its address.</p>".encode()
SCRIPT_SHA = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()


class LoopbackServer(HTTPServer):
    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        connection, address = super().get_request()
        connection.settimeout(1)
        return connection, address

    def handle_error(self, request: object, client_address: object) -> None:
        """Never let stdlib exception output disclose a callback request target."""


def receive_callback(
    session: CallbackSession,
    clock: Callable[[], datetime],
    ready: Callable[[], None],
) -> AuthorizationCode:
    """An activated, exact registered URI accepts once; at most twenty requests/five minutes."""
    result: list[AuthorizationCode] = []
    attempts = [0]

    class Handler(BaseHTTPRequestHandler):
        def handle_one_request(self) -> None:
            attempts[0] += 1
            super().handle_one_request()

        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_POST(self) -> None:
            self.send_error(405, "Local callback requires GET")

        def do_GET(self) -> None:
            status = 403
            try:
                hosts = self.headers.get_all("Host", [])
                if (
                    len(hosts) != 1
                    or self.headers.get("Transfer-Encoding")
                    or self.headers.get("Content-Length", "0") != "0"
                ):
                    raise OAuthRefused("oauth_callback_headers_invalid")
                result.append(session.accept(hosts[0], self.path, clock()))
                status = 200
            except OAuthRefused:
                pass
            self._respond(status)

        def send_error(
            self, code: int, message: str | None = None, explain: str | None = None
        ) -> None:
            """Stdlib parser errors otherwise reflect request lines containing private codes."""
            self._respond(code)

        def _respond(self, status: int) -> None:
            self.send_response(status)
            for key, value in {
                "Content-Type": "text/html; charset=utf-8",
                "Content-Length": str(len(BODY)),
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "Connection": "close",
                "Content-Security-Policy": f"default-src 'none'; script-src 'sha256-{SCRIPT_SHA}'; frame-ancestors 'none'",
            }.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(BODY)

    try:
        if session.active_at is None or session.used:
            raise OAuthRefused("oauth_listener_requires_active_owner_session")
        deadline = time.monotonic() + 300
        with LoopbackServer(("127.0.0.1", session.port), Handler) as server:
            server.timeout = 0.25
            ready()
            for _ in range(1200):
                if (
                    session.used
                    or result
                    or attempts[0] >= 20
                    or time.monotonic() >= deadline
                    or (clock() - session.active_at).total_seconds() >= 300
                ):
                    break
                server.handle_request()
            if not result:
                raise OAuthRefused("oauth_callback_not_completed")
        return result[0]
    except Exception:
        raise OAuthRefused("oauth_local_callback_refused") from None
