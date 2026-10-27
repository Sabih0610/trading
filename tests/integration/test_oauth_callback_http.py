"""Malformed HTTP must not reflect a callback code even through stdlib error responses."""

import http.client
import socket
import threading
from datetime import UTC, datetime

from tb.ingest.broker.onboarding.callback import receive_callback
from tb.ingest.broker.onboarding.models import CallbackSession


def test_http_parser_errors_do_not_reflect_code_or_private_callback_path():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    session = CallbackSession.prepare(port)
    session.activate(datetime.now(UTC))
    responses, clients = [], []

    def client():
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            target = session.path + "?code=owned-parser-decoy"
            sock.sendall(
                f"GET {target} EXTRA EXTRA HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode()
            )
            chunks = []
            while chunk := sock.recv(8192):
                chunks.append(chunk)
            responses.append(b"".join(chunks))
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request("GET", session.path + "?code=owned-good-code")
            response = connection.getresponse()
            response.read()
        finally:
            connection.close()

    def ready():
        t = threading.Thread(target=client)
        clients.append(t)
        t.start()

    code = receive_callback(session, lambda: datetime.now(UTC), ready)
    for t in clients:
        t.join(timeout=5)
    assert code.consume(datetime.now(UTC)) == "owned-good-code"
    assert responses and all(
        b"owned-parser-decoy" not in data and session.path.encode() not in data
        for data in responses
    )
