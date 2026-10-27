"""Inert status by default; explicit owner actions after approval, or owned offline rehearsal."""

from __future__ import annotations

import argparse
import getpass
import json
import secrets
import tempfile
import webbrowser
from datetime import UTC, datetime
from pathlib import Path

from pydantic import SecretStr

from tb.core.config import repo_root
from tb.ingest.broker.onboarding.callback import receive_callback
from tb.ingest.broker.onboarding.models import CallbackSession, OAuthRefused
from tb.ingest.broker.onboarding.private import PrivateEnv
from tb.ingest.broker.onboarding.service import FixedTokenEndpoint, TokenService, verify_grant
from tb.ingest.broker.onboarding.workflow import configuration, prepare, save_tokens, stored_tokens
from tb.ingest.broker.transport import DemoJsonChannel

PUBLIC_REFUSALS = {
    "oauth_disabled_missing_or_changed_private_configuration": "private_configuration_missing_or_changed",
    "oauth_genuine_network_not_authorized": "owner_authorization_or_approval_missing",
    "oauth_prepare_and_register_new_callback_first": "fresh_registered_callback_required",
    "oauth_local_callback_refused": "local_callback_refused",
    "oauth_token_exchange_refused": "token_exchange_refused",
    "oauth_demo_grant_verification_refused": "view_only_demo_grant_refused",
    "oauth_owner_account_confirmation_refused": "owner_confirmation_refused",
    "oauth_private_state_unreadable_or_invalid": "private_storage_invalid",
    "oauth_private_transaction_refused": "private_storage_commit_refused",
    "oauth_owner_session_already_active": "another_local_owner_session_active",
}


def authorize(env: PrivateEnv, *, after_approval: bool, refresh: bool = False) -> None:
    """Future owner-operated auth only. No retries, quote collection or broker facade startup."""
    with env.session_lease():
        _authorize(env, after_approval=after_approval, refresh=refresh)


def _authorize(env: PrivateEnv, *, after_approval: bool, refresh: bool) -> None:
    snapshot = env.read()
    keys, account, broker, consent = configuration(snapshot, explicit=after_approval)
    consent.require()
    service = TokenService(FixedTokenEndpoint(consent), keys)
    if refresh:
        tokens = service.refresh(stored_tokens(snapshot), datetime.now(UTC))
    else:
        if snapshot.values.get("CTRADER_DEMO_OAUTH_CALLBACK_STATE") != "prepared":
            raise OAuthRefused("oauth_prepare_and_register_new_callback_first")
        session = CallbackSession(
            SecretStr(snapshot.values.get("CTRADER_DEMO_OAUTH_REDIRECT_URI", ""))
        )
        # Persist spent status before opening a browser. A crash cannot rearm this URI.
        env.update(snapshot, {"CTRADER_DEMO_OAUTH_CALLBACK_STATE": "spent"})
        session.activate(datetime.now(UTC))

        def open_owner_browser() -> None:
            if not webbrowser.open(session.authorization_url(keys), new=1):
                raise OAuthRefused("oauth_owner_browser_unavailable")

        code = receive_callback(session, lambda: datetime.now(UTC), open_owner_browser)
        tokens = service.exchange(code, session, datetime.now(UTC))
    consent.require()
    proof = verify_grant(DemoJsonChannel(), keys, tokens, account, broker, datetime.now(UTC))
    confirmation = getpass.getpass(
        "Returned grant matches your configured demo account. Re-enter its ID privately to confirm: "
    )
    if not secrets.compare_digest(confirmation, account):
        raise OAuthRefused("oauth_owner_account_confirmation_refused")
    save_tokens(env, tokens, proof, datetime.now(UTC))


def main() -> None:
    """Never accept keys/codes/tokens as command-line arguments or print their values."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "prepare", "authorize", "refresh", "rehearsal"],
    )
    parser.add_argument("--after-approval", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.action == "rehearsal":
            from tb.ingest.broker.onboarding.fixtures import owned_rehearsal

            with tempfile.TemporaryDirectory(prefix="tb-oauth-owned-") as folder:
                root = Path(folder).resolve()
                if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
                    raise OAuthRefused("oauth_owned_temporary_path_refused")
                result = owned_rehearsal(root)
            print(json.dumps(result))
            return
        env = PrivateEnv(repo_root())
        if args.action == "status":
            snapshot = env.read()
            configured = all(
                snapshot.values.get("CTRADER_DEMO_" + name)
                for name in ["CLIENT_ID", "CLIENT_SECRET", "ACCOUNT_ID", "BROKER_PIN"]
            )
            print(
                json.dumps(
                    {
                        "mode": "oauth_preparation",
                        "configured": configured,
                        "private_token_pair_present": all(
                            snapshot.values.get("CTRADER_DEMO_" + name)
                            for name in ["ACCESS_TOKEN", "REFRESH_TOKEN"]
                        ),
                        "stored_permission_is_view": snapshot.values.get(
                            "CTRADER_DEMO_TOKEN_PERMISSION"
                        )
                        == "SCOPE_VIEW",
                        "genuine_connectivity": "UNVERIFIED",
                        "automatic_refresh": False,
                        "quotes_enabled": False,
                        "external_orders_enabled": False,
                    }
                )
            )
        elif args.action == "prepare":
            prepare(env, port=args.port)
            print(
                "Prepared a new private one-use callback URI in root .env. Register it exactly after approval; do not share it."
            )
        else:
            authorize(env, after_approval=args.after_approval, refresh=args.action == "refresh")
            print(
                "Private view-only demo authorization stored. No quote session or paper integration started."
            )
    except OAuthRefused as error:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reason": PUBLIC_REFUSALS.get(str(error), "local_authorization_refused"),
                }
            )
        )
        raise SystemExit(2) from None
    except Exception:
        # Generic CLI boundary includes unexpected OS/browser/ACL errors, never raw exception text.
        print(
            "OAuth action refused. Check private configuration, app approval, exact callback registration and owner pins; no credentials were logged."
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
