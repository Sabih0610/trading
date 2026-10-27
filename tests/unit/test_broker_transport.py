"""Real channel logic over an owned socket double; no network or provider credentials."""

import json
import logging
from collections import deque

import pytest

from tb.ingest.broker.models import BrokerRefused
from tb.ingest.broker.transport import DEMO_URL, READ_FIELDS, DemoJsonChannel


class SocketDouble:
    def __init__(self):
        self.sent = []
        self.replies = deque()
        self.closed = False

    def send(self, text):
        value = json.loads(text)
        self.sent.append(value)
        self.replies.append(
            json.dumps(
                {
                    "payloadType": value["payloadType"] + 1,
                    "clientMsgId": value["clientMsgId"],
                    "payload": {},
                }
            )
        )

    def recv(self, timeout):
        assert 0 < timeout <= 2
        return self.replies.popleft()

    def close(self):
        self.closed = True


def test_demo_host_tls_no_proxy_and_wire_logging_disabled(monkeypatch, caplog):
    socket = SocketDouble()
    options = {}

    def connect(uri, **kwargs):
        assert uri == DEMO_URL == "wss://demo.ctraderapi.com:5036"
        options.update(kwargs)
        return socket

    monkeypatch.setattr("tb.ingest.broker.transport.connect", connect)
    caplog.set_level(logging.DEBUG)
    channel = DemoJsonChannel()
    assert channel.request(2100, {"clientId": "OWNED-CLIENT", "clientSecret": "OWNED-SECRET"}) == {}
    assert options["proxy"] is None and options["logger"].disabled
    assert options["max_size"] == 262144 and options["max_queue"] == 16
    assert "OWNED-SECRET" not in caplog.text
    for kind in [2106, 2109, 2110, 2111, 2140, 2172, 9999]:
        before = len(socket.sent)
        with pytest.raises(BrokerRefused):
            channel.request(kind, {"ctidTraderAccountId": 777})
        assert len(socket.sent) == before
    assert all(v["payloadType"] in READ_FIELDS for v in socket.sent)
    channel.close()


def test_correlated_reply_keeps_prior_spot_event_bounded(monkeypatch):
    socket = SocketDouble()
    event = {"payloadType": 2131, "payload": {"symbolId": 101}}
    socket.replies.append(json.dumps(event))
    monkeypatch.setattr("tb.ingest.broker.transport.connect", lambda *a, **kw: socket)
    channel = DemoJsonChannel()
    assert channel.request(2121, {"ctidTraderAccountId": 777}) == {}
    received = channel.receive()
    assert (
        received["payloadType"] == event["payloadType"] and received["payload"] == event["payload"]
    )
    assert received["_received_at"].utcoffset().total_seconds() == 0
    channel.close()


@pytest.mark.parametrize(
    "case", ["wrong_correlation", "unknown", "invalid_json", "revoked", "overflow"]
)
def test_protocol_errors_refuse_and_close_without_native_error_text(monkeypatch, case):
    socket = SocketDouble()
    messages = {
        "wrong_correlation": [{"payloadType": 2122, "clientMsgId": "wrong", "payload": {}}],
        "unknown": [{"payloadType": 9999, "payload": {"description": "OWNED-NATIVE-SECRET"}}],
        "revoked": [{"payloadType": 2147, "payload": {"description": "OWNED-NATIVE-SECRET"}}],
        "overflow": [{"payloadType": 2131, "payload": {}}] * 130,
    }
    if case == "invalid_json":
        socket.replies.append("OWNED-NATIVE-SECRET")
    else:
        socket.replies.extend(json.dumps(v) for v in messages[case])
    monkeypatch.setattr("tb.ingest.broker.transport.connect", lambda *a, **kw: socket)
    channel = DemoJsonChannel()
    with pytest.raises(BrokerRefused) as error:
        channel.request(2121, {"ctidTraderAccountId": 777})
    assert socket.closed and "OWNED-NATIVE-SECRET" not in str(error.value)


def test_rate_and_total_lifetime_limits_are_finite(monkeypatch):
    socket = SocketDouble()
    instant = [0.0]
    monkeypatch.setattr("tb.ingest.broker.transport.connect", lambda *a, **kw: socket)
    monkeypatch.setattr("tb.ingest.broker.transport.time.monotonic", lambda: instant[0])
    channel = DemoJsonChannel()
    for _ in range(10):
        assert channel.request(2121, {"ctidTraderAccountId": 777}) == {}
    with pytest.raises(BrokerRefused):
        channel.request(2121, {"ctidTraderAccountId": 777})
    channel = DemoJsonChannel()
    instant[0] = 61
    with pytest.raises(BrokerRefused):
        channel.request(2121, {"ctidTraderAccountId": 777})
