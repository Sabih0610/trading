"""Private configuration, one-use preparation and proof-bound token persistence."""

from __future__ import annotations

from datetime import datetime

from pydantic import SecretStr

from tb.ingest.broker.book import integer
from tb.ingest.broker.models import SERVER
from tb.ingest.broker.onboarding.models import (
    AppKeys,
    CallbackSession,
    OAuthRefused,
    TokenPair,
    private_value,
    utc,
)
from tb.ingest.broker.onboarding.private import PrivateEnv, PrivateSnapshot
from tb.ingest.broker.onboarding.service import NetworkConsent, VerifiedGrant, binding


def configuration(
    snapshot: PrivateSnapshot, *, explicit: bool = False
) -> tuple[AppKeys, str, str, NetworkConsent]:
    """Use only explicitly configured app/account pins; no discovery or account switching."""
    try:
        v = snapshot.values
        keys = AppKeys(
            SecretStr(v.get("CTRADER_DEMO_CLIENT_ID", "")),
            SecretStr(v.get("CTRADER_DEMO_CLIENT_SECRET", "")),
        )
        keys.require()
        if v.get("CTRADER_DEMO_REQUESTED_SCOPE", "accounts") not in {"", "accounts"}:
            raise ValueError
        account, broker = v.get("CTRADER_DEMO_ACCOUNT_ID", ""), v.get("CTRADER_DEMO_BROKER_PIN", "")
        if str(integer(account)) != account or not 1 <= len(broker) <= 100:
            raise ValueError
        for name, expected in {
            "CTRADER_DEMO_ACCOUNT_FINGERPRINT": binding(f"{SERVER}:{account}"),
            "CTRADER_DEMO_OAUTH_APPLICATION_BINDING": binding(keys.client_id.get_secret_value()),
            "CTRADER_DEMO_VERIFIED_BROKER": broker,
        }.items():
            if v.get(name) and v[name] != expected:
                raise ValueError
        consent = NetworkConsent(
            v.get("CTRADER_DEMO_APPLICATION_APPROVED") == "true",
            v.get("CTRADER_DEMO_OAUTH_ENABLED") == "true",
            explicit,
        )
        return keys, account, broker, consent
    except Exception:
        raise OAuthRefused("oauth_disabled_missing_or_changed_private_configuration") from None


def prepare(env: PrivateEnv, *, port: int = 8765) -> None:
    """Offline-only preparation, with no copied keys or automatic portal/browser interaction."""
    with env.session_lease():
        snapshot = env.read()
        configuration(snapshot)
        session = CallbackSession.prepare(port)
        env.update(
            snapshot,
            {
                "CTRADER_DEMO_OAUTH_REDIRECT_URI": session.redirect.get_secret_value(),
                "CTRADER_DEMO_OAUTH_CALLBACK_STATE": "prepared",
            },
        )


def save_tokens(env: PrivateEnv, tokens: TokenPair, proof: VerifiedGrant, now: datetime) -> None:
    """Commit a complete verified pair with expiry/pin; never store a raw authorization code."""
    snapshot = env.read()
    keys, account, broker, _ = configuration(snapshot)
    tokens.require_current(now)
    if (
        proof.account != account
        or proof.broker != broker
        or proof.server != SERVER
        or proof.scope.name != "SCOPE_VIEW"
        or not 0 <= (utc(now) - proof.checked_at).total_seconds() <= 30
        or proof.access_binding != binding(tokens.access.get_secret_value())
        or proof.application_binding != binding(keys.client_id.get_secret_value())
    ):
        raise OAuthRefused("oauth_token_storage_identity_proof_mismatch")
    env.update(
        snapshot,
        {
            "CTRADER_DEMO_ACCESS_TOKEN": tokens.access.get_secret_value(),
            "CTRADER_DEMO_REFRESH_TOKEN": tokens.refresh.get_secret_value(),
            "CTRADER_DEMO_ACCESS_EXPIRES_AT": tokens.expires_at.isoformat(),
            "CTRADER_DEMO_TOKEN_ISSUED_AT": tokens.issued_at.isoformat(),
            "CTRADER_DEMO_TOKEN_TYPE": "bearer",
            "CTRADER_DEMO_REQUESTED_SCOPE": "accounts",
            "CTRADER_DEMO_ACCOUNT_FINGERPRINT": proof.fingerprint,
            "CTRADER_DEMO_VERIFIED_BROKER": proof.broker,
            "CTRADER_DEMO_OAUTH_APPLICATION_BINDING": proof.application_binding,
            "CTRADER_DEMO_TOKEN_PERMISSION": "SCOPE_VIEW",
            "CTRADER_DEMO_ACCOUNT_ACCESS_RIGHTS": proof.access_rights.name,
            "CTRADER_DEMO_OAUTH_VERIFIED_AT": proof.checked_at.isoformat(),
            "CTRADER_DEMO_OAUTH_CALLBACK_STATE": "consumed",
        },
    )


def stored_tokens(snapshot: PrivateSnapshot) -> TokenPair:
    """Malformed or incomplete state refuses; there is no secret backup or automatic repair."""
    try:
        v = snapshot.values
        tokens = TokenPair(
            private_value(v["CTRADER_DEMO_ACCESS_TOKEN"]),
            private_value(v["CTRADER_DEMO_REFRESH_TOKEN"]),
            utc(datetime.fromisoformat(v["CTRADER_DEMO_TOKEN_ISSUED_AT"])),
            utc(datetime.fromisoformat(v["CTRADER_DEMO_ACCESS_EXPIRES_AT"])),
        )
        if (
            v["CTRADER_DEMO_TOKEN_TYPE"] != "bearer"
            or v["CTRADER_DEMO_TOKEN_PERMISSION"] != "SCOPE_VIEW"
            or tokens.expires_at <= tokens.issued_at
        ):
            raise ValueError
        return tokens
    except Exception:
        raise OAuthRefused("oauth_stored_token_state_invalid") from None
