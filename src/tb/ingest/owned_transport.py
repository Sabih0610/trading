"""Explicit in-memory HTTP fixtures; Python network calls inside handlers are denied."""

from __future__ import annotations

import sys
from typing import Any

import httpx

from tb.ingest.mt5.models import FeedUnavailable

_installed = False
_fixture_depth = 0


def _deny_socket(event: str, args: tuple[Any, ...]) -> None:
    if _fixture_depth and event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise FeedUnavailable("owned_http_fixture_network_denied")


class _OwnedTransport(httpx.BaseTransport):
    def __init__(self, mock: httpx.MockTransport) -> None:
        self.mock = mock

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        global _fixture_depth
        _fixture_depth += 1
        try:
            response = self.mock.handle_request(request)
            try:
                body = bytearray()
                for chunk in response.iter_bytes(8192):
                    body.extend(chunk)
                    if len(body) > 131072:
                        raise FeedUnavailable("twelve_data_response_too_large")
                return httpx.Response(
                    response.status_code, headers=response.headers, content=bytes(body)
                )
            finally:
                response.close()
        finally:
            _fixture_depth -= 1

    def close(self) -> None:
        self.mock.close()


def owned_transport(transport: httpx.MockTransport) -> httpx.BaseTransport:
    """Exact mock only; handler and response iteration execute under socket denial.

    This prevents accidental synchronous Python socket use, including a handler
    that forwards requests; it is not an OS firewall against hostile Python code.
    """
    global _installed
    if type(transport) is not httpx.MockTransport:
        raise FeedUnavailable("owned_http_fixture_exact_mock_required")
    if not _installed:
        sys.addaudithook(_deny_socket)
        _installed = True
    return _OwnedTransport(transport)
