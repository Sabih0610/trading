"""Explicit fictional source-clock evidence for offline mechanics, never genuine qualification."""

import hashlib
from datetime import UTC, datetime

import pytest

from tb.ingest.clock_profiles import ClockProfile


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
