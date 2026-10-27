"""Opt-in CI Python network guard; only owned loopback test servers are permitted.

This is an accident guard for the reviewed offline suite, not an OS security boundary.
Registry setup precedes activation. No providers, credentials or model clients are initialized.
"""

import ipaddress
import os
import sys


def offline_audit(event, args):
    if event not in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        return
    address = args[1] if event != "socket.getaddrinfo" else args[:2]
    if not isinstance(address, tuple) or len(address) < 2:
        raise RuntimeError("Offline validation refused a non-IP socket")
    host, port = address[:2]
    if isinstance(host, bytes):
        host = host.decode("ascii")
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback or port == 22346:
        raise RuntimeError("Offline validation refused external/provider network access")


if os.environ.get("TB_OFFLINE_VALIDATION") == "1":
    sys.addaudithook(offline_audit)
