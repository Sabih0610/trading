"""Explicit fictional source-clock evidence for offline mechanics, never genuine qualification."""

import hashlib
import ipaddress
import os
import socket
from datetime import UTC, datetime

import pytest

from tb.ingest.clock_profiles import ClockProfile

os.environ["MLFLOW_DISABLE_TELEMETRY"] = "true"
os.environ["DO_NOT_TRACK"] = "1"


@pytest.fixture(autouse=True)
def deny_external_sockets(monkeypatch, request):
    """Default tests may use owned loopback servers, never external DNS or sockets."""
    if request.node.get_closest_marker("live"):
        return
    original_resolve = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto

    def allowed(host):
        if isinstance(host, bytes):
            host = host.decode("ascii")
        if host in (None, "localhost"):
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise AssertionError("Default tests deny non-loopback network access")

    def resolve(host, *args, **kwargs):
        allowed(host)
        return original_resolve(host, *args, **kwargs)

    def connect(sock, address):
        allowed(address[0])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        allowed(address[0])
        return original_connect_ex(sock, address)

    def sendto(sock, data, *args):
        allowed(args[-1][0])
        return original_sendto(sock, data, *args)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", sendto)


@pytest.fixture
def clock_profile_factory():
    def make(**changes):
        data = dict(
            profile_id="fixture-clock.v1",
            provider="mt5_demo",
            broker="Synthetic fixture",
            server="Offline-Demo",
            environment="demo",
            instruments=["EURUSD", "XAUUSD"],
            semantics="utc_epoch",
            state="VERIFIED",
            issued_at=datetime(2020, 1, 1, tzinfo=UTC),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            verified_at=datetime(2020, 1, 2, tzinfo=UTC),
            reviewed_by="offline-test-only",
            validation_samples=3,
            validation_started=datetime(2020, 1, 1, 1, tzinfo=UTC),
            validation_ended=datetime(2020, 1, 1, 1, 0, 10, tzinfo=UTC),
            independent_utc_sources=["mock-clock-a", "mock-clock-b"],
            maximum_residual_seconds=0,
            validated_kinds=["quote", "tick", "candle"],
            validation_environment="fixture",
        )
        data.update(changes)
        data.setdefault(
            "evidence",
            [
                dict(
                    kind="official_spec",
                    reference="https://example.invalid/fixture-spec",
                    provider=data["provider"],
                    server=data["server"],
                    captured_at=data["issued_at"],
                    content_sha256=hashlib.sha256(
                        b"fictional offline clock specification"
                    ).hexdigest(),
                )
            ],
        )
        return ClockProfile.model_validate(data)

    return make
