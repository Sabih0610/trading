"""Root .env only, private ACLs, optimistic version check and atomic complete-pair storage."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from tb.core.leases import WriterBusy, writer_lease
from tb.ingest.broker.onboarding.models import OAuthRefused
from tb.ingest.broker.onboarding.service import binding


def _command(args: list[str], *, extra_env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        args,
        env={**os.environ, **(extra_env or {})},
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if result.returncode:
        raise OAuthRefused("oauth_private_acl_command_failed")
    return result.stdout


@lru_cache(maxsize=1)
def owner_sid() -> str:
    """Resolve the current Windows user once, without using a username in generated artifacts."""
    for row in csv.reader(io.StringIO(_command(["whoami", "/user", "/fo", "csv", "/nh"]))):
        if len(row) == 2 and re.fullmatch(r"S-1-[0-9-]+", row[1]):
            return row[1]
    raise OAuthRefused("oauth_private_owner_sid_unavailable")


def restrict(path: Path) -> None:
    """Apply privacy to an empty staging file before it can receive any secret bytes."""
    if os.name == "nt":
        _command(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{owner_sid()}:(F)",
                "*S-1-5-18:(F)",
            ]
        )
    else:
        path.chmod(0o600)
    require_private(path)


def require_private(path: Path) -> None:
    """Refuse weak permissions; never silently alter existing private credential files."""
    if path.is_symlink() or path.resolve() != path.absolute():
        raise OAuthRefused("oauth_private_path_link_refused")
    if sys.platform == "win32":
        command = "$a=Get-Acl -LiteralPath $env:TB_OAUTH_ACL_FILE; @{owner=$a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value; protected=$a.AreAccessRulesProtected; allow=@($a.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) | Where-Object {$_.AccessControlType -eq 'Allow'} | ForEach-Object {$_.IdentityReference.Value})} | ConvertTo-Json -Compress"
        result = json.loads(
            _command(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
                extra_env={"TB_OAUTH_ACL_FILE": str(path)},
            )
        )
        allowed = set(result["allow"])
        if (
            result["owner"] != owner_sid()
            or result["protected"] is not True
            or not allowed
            or not allowed <= {owner_sid(), "S-1-5-18"}
            or owner_sid() not in allowed
        ):
            raise OAuthRefused("oauth_private_acl_not_owner_system_only")
    elif path.stat().st_uid != int(os.getuid()) or path.stat().st_mode & 0o077:
        raise OAuthRefused("oauth_private_permissions_too_broad")


@dataclass(frozen=True, repr=False)
class PrivateSnapshot:
    values: dict[str, str]
    sha256: str
    lines: tuple[str, ...]


class PrivateEnv:
    """No secondary token file, backup, persistent code or secret-bearing recovery journal."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.path = self.root / ".env"

    @contextmanager
    def session_lease(self) -> Iterator[None]:
        """Prevent concurrent preparation/authorization/refresh, including different ports."""
        try:
            with writer_lease(self.root / "work/ctrader_oauth/session.lock"):
                yield
        except WriterBusy:
            raise OAuthRefused("oauth_owner_session_already_active") from None

    def read(self) -> PrivateSnapshot:
        """Strictly parse private state, masking all parsing/permission errors."""
        try:
            if self.path.is_symlink():
                raise ValueError
            if not self.path.exists():
                return PrivateSnapshot({}, binding(""), ())
            require_private(self.path)
            if self.path.stat().st_size > 65536:
                raise ValueError
            text = self.path.read_text(encoding="utf-8")
            values: dict[str, str] = {}
            for line in text.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(.*)", line)
                if not match or match[1] in values:
                    raise ValueError
                value = match[2]
                if value.startswith('"'):
                    value = json.loads(value)
                elif value.startswith("'"):
                    if not value.endswith("'"):
                        raise ValueError
                    value = value[1:-1]
                if not isinstance(value, str) or any(c in value for c in "\r\n\x00"):
                    raise ValueError
                values[match[1]] = value
            return PrivateSnapshot(values, binding(text), tuple(text.splitlines()))
        except Exception:
            raise OAuthRefused("oauth_private_state_unreadable_or_invalid") from None

    def update(
        self,
        expected: PrivateSnapshot,
        changes: dict[str, str],
        *,
        fault: Callable[[str], None] | None = None,
    ) -> None:
        """Full token/expiry/pin updates commit by one private replacement, or refuse."""
        temporary: Path | None = None
        try:
            if not self.root.is_dir() or any(
                not re.fullmatch(r"CTRADER_DEMO_[A-Z_]+", k)
                or not isinstance(v, str)
                or len(v) > 8192
                or any(c in v for c in "\r\n\x00")
                for k, v in changes.items()
            ):
                raise ValueError
            with writer_lease(self.root / "work/ctrader_oauth/writer.lock"):
                current = self.read()
                if current.sha256 != expected.sha256:
                    raise ValueError
                lines = [line for line in current.lines if line.partition("=")[0] not in changes]
                text = (
                    "\n".join(
                        [
                            *lines,
                            *(
                                f"{k}={json.dumps(v, ensure_ascii=True)}"
                                for k, v in sorted(changes.items())
                            ),
                        ]
                    )
                    + "\n"
                )
                if len(text.encode()) > 65536:
                    raise ValueError
                fd, name = tempfile.mkstemp(prefix=".env.", dir=self.root)
                temporary = Path(name)
                os.close(fd)
                restrict(temporary)
                with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write(text)
                    handle.flush()
                    os.fsync(handle.fileno())
                if fault:
                    fault("before_replace")
                os.replace(temporary, self.path)
                if fault:
                    fault("after_replace")
                require_private(self.path)
        except Exception:
            raise OAuthRefused("oauth_private_transaction_refused") from None
        finally:
            if temporary and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    raise OAuthRefused("oauth_private_staging_cleanup_refused") from None
