"""Default tests refuse outbound traffic before DNS resolution or connection."""

import socket

import pytest


@pytest.mark.parametrize("host", ["example.invalid", "192.0.2.1", "2001:db8::1"])
def test_non_loopback_dns_and_connections_are_denied(host):
    with pytest.raises(AssertionError, match="non-loopback"):
        socket.getaddrinfo(host, 443)
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="non-loopback"):
            connection.connect((host, 443))
        with pytest.raises(AssertionError, match="non-loopback"):
            connection.connect_ex((host, 443))
        with pytest.raises(AssertionError, match="non-loopback"):
            connection.sendto(b"fixture", (host, 443))


def test_mlflow_has_no_telemetry_client():
    from mlflow.telemetry import get_telemetry_client

    assert get_telemetry_client() is None
