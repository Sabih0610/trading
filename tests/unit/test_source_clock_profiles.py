"""Versioning, authoritative evidence, effective periods and source-clock failure tests."""

from datetime import UTC, datetime, timedelta

import pytest

from tb.ingest.clock_profiles import ClockPeriod, ClockRefused, ClockSequence, ClockState
from tb.ingest.mt5.adapter import MT5Feed
from tb.ingest.mt5.fake import FakeReader
from tb.ingest.mt5.models import FeedConfig, FeedUnavailable
from tb.ingest.mt5.storage import FeedStore, record_id

NOW = datetime(2024, 6, 3, 10, tzinfo=UTC)


def normalize(profile, at, **overrides):
    args = dict(
        raw_representation=at.isoformat(),
        provider="mt5_demo",
        broker="Synthetic fixture",
        server="Offline-Demo",
        environment="demo",
        instrument="EURUSD",
        build=6060,
        identity_fingerprint="a" * 64,
        now=NOW,
        kind="quote",
    )
    args.update(overrides)
    return profile.normalize(at, **args)


@pytest.mark.parametrize("offset", [10800, 20700, -12600, 0])
def test_exact_effective_offset_and_non_hour_rule(clock_profile_factory, offset):
    profile = clock_profile_factory(
        semantics="broker_wall_epoch",
        periods=[
            dict(start="2024-01-01T00:00:00Z", end="2025-01-01T00:00:00Z", offset_seconds=offset)
        ],
    )
    raw = NOW + timedelta(seconds=offset)
    stamp = normalize(profile, raw)
    assert stamp.raw_at == raw and stamp.normalized_at == NOW
    assert stamp.profile_digest == profile.digest


@pytest.mark.parametrize("state", ["UNVERIFIED", "PROVISIONAL", "EXPIRED", "INVALID"])
def test_unverified_or_provisional_profiles_never_convert(clock_profile_factory, state):
    profile = clock_profile_factory(state=state)
    with pytest.raises(ClockRefused):
        normalize(profile, NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"evidence": []},
        {"validation_samples": 2},
        {"maximum_residual_seconds": 3},
        {"independent_utc_sources": ["a", "a"]},
        {"reviewed_by": None},
        {"validation_ended": "2020-01-01T01:00:01Z"},
    ],
)
def test_verified_flag_requires_proof(clock_profile_factory, changes):
    with pytest.raises(ValueError, match="VERIFIED"):
        clock_profile_factory(**changes)


def test_unchecked_state_copy_cannot_promote_without_evidence(clock_profile_factory):
    provisional = clock_profile_factory(state="PROVISIONAL", evidence=[])
    promoted = provisional.model_copy(update={"state": ClockState.VERIFIED})
    with pytest.raises(ClockRefused, match="evidence_invalid"):
        normalize(promoted, NOW)


def test_expiration_build_provider_instrument_and_period_scope(clock_profile_factory):
    profile = clock_profile_factory(builds=[6060], instruments=["EURUSD"])
    assert profile.effective_state(datetime(2030, 1, 1, tzinfo=UTC)) == ClockState.EXPIRED
    for kw in (
        {"provider": "other"},
        {"server": "different"},
        {"build": 6281},
        {"instrument": "XAUUSD"},
        {"now": datetime(2030, 1, 1, tzinfo=UTC)},
    ):
        with pytest.raises(ClockRefused):
            normalize(profile, NOW, **kw)


def test_iana_ambiguous_fold_gap_and_dst_offsets(clock_profile_factory):
    p = clock_profile_factory(semantics="broker_wall_epoch", timezone="America/New_York")
    assert normalize(p, datetime(2024, 7, 1, 10, tzinfo=UTC)).normalized_at.hour == 14
    assert normalize(p, datetime(2024, 1, 1, 10, tzinfo=UTC)).normalized_at.hour == 15
    for raw in (datetime(2024, 3, 10, 2, 30, tzinfo=UTC), datetime(2024, 11, 3, 1, 30, tzinfo=UTC)):
        with pytest.raises(ClockRefused, match="ambiguous_or_uncovered"):
            normalize(p, raw)


def test_period_specific_fold_gap_no_current_offset_for_history(clock_profile_factory):
    periods = [
        ClockPeriod(start="2024-01-01T00:00:00Z", end="2024-03-31T01:00:00Z", offset_seconds=7200),
        ClockPeriod(start="2024-03-31T01:00:00Z", end="2024-10-27T01:00:00Z", offset_seconds=10800),
        ClockPeriod(start="2024-10-27T01:00:00Z", end="2025-01-01T00:00:00Z", offset_seconds=7200),
    ]
    p = clock_profile_factory(semantics="broker_wall_epoch", periods=periods)
    assert normalize(p, datetime(2024, 1, 1, 12, tzinfo=UTC)).normalized_at.hour == 10
    assert normalize(p, datetime(2024, 7, 1, 12, tzinfo=UTC)).normalized_at.hour == 9
    for raw in (
        datetime(2024, 3, 31, 3, 30, tzinfo=UTC),
        datetime(2024, 10, 27, 3, 30, tzinfo=UTC),
        datetime(2023, 1, 1, tzinfo=UTC),
    ):
        with pytest.raises(ClockRefused):
            normalize(p, raw)


def test_clock_sequence_duplicate_delay_out_of_order_and_shift():
    seq = ClockSequence()
    seq.observe(NOW, NOW)
    seq.observe(NOW, NOW + timedelta(seconds=5))
    for source, receipt in (
        (NOW - timedelta(seconds=1), NOW + timedelta(seconds=6)),
        (NOW + timedelta(hours=1), NOW + timedelta(seconds=6)),
        (NOW, NOW - timedelta(seconds=1)),
    ):
        with pytest.raises(ClockRefused):
            seq.observe(source, receipt)


def test_effective_history_range_is_independent_of_profile_freshness(clock_profile_factory):
    profile = clock_profile_factory(
        effective_from="2024-01-01T00:00:00Z", effective_to="2025-01-01T00:00:00Z"
    )
    with pytest.raises(ClockRefused, match="effective_range"):
        normalize(profile, datetime(2023, 1, 1, tzinfo=UTC))
    assert normalize(profile, NOW).normalized_at == NOW


def test_missing_genuine_profile_never_yields_a_qualified_quote(tmp_path):
    reader = FakeReader(tmp_path / "terminal/terminal64.exe", lambda: NOW)
    reader.synthetic = False
    feed = MT5Feed(
        reader,
        FeedConfig(),
        terminal_path=reader.path,
        login=str(reader.login),
        server=reader.server,
        clock=lambda: NOW,
    )
    feed.connect()
    with pytest.raises(FeedUnavailable, match="profile_unavailable"):
        feed.quote("EURUSD")


def test_independent_instrument_admission_with_one_missing_quote(tmp_path, clock_profile_factory):
    from types import SimpleNamespace
    from unittest.mock import patch

    from tb.ingest.mt5.collector import Collector
    from tb.ingest.mt5.qualification import AdmissionMonitor

    reader = FakeReader(tmp_path / "terminal/terminal64.exe", lambda: NOW)
    reader.info_overrides.update(visible=True, select=True)
    feed = MT5Feed(
        reader,
        FeedConfig(max_polls=1, max_rows=2),
        terminal_path=reader.path,
        login=str(reader.login),
        server=reader.server,
        clock=lambda: NOW,
        clock_profile=clock_profile_factory(),
    )
    feed.connect()
    native = SimpleNamespace(dangerous_shell_tool_available=False, discover=lambda: [])

    def call(name, args):
        if name == "terminal_get_info":
            return {"native_mcp_trading_permission": False}
        if name == "get_trading_account_info":
            return {"fingerprint": feed.verify().fingerprint}
        return {"utc_time": NOW.isoformat()}

    native.call = call
    original = reader.read

    def missing_gold(name, *args, **kwargs):
        if name == "symbol_info_tick" and args[0] == "XAUUSD":
            return None
        return original(name, *args, **kwargs)

    reference = [
        {"accepted": True, "received_utc": NOW.isoformat(), "reference_utc": NOW.isoformat()}
    ]
    with (
        patch.object(reader, "read", side_effect=missing_gold),
        patch("tb.ingest.mt5.qualification.independent_utc", return_value=reference),
    ):
        result = AdmissionMonitor(feed, native)()
    assert result.clock_passed and result.instruments == {"EURUSD": True, "XAUUSD": False}
    store = FeedStore(tmp_path, feed.config, code_version="fixture")
    try:
        collector = Collector(feed, store, tmp_path / "export", clock=lambda: NOW)
        collector.admission_result = (
            result  # Exercise the mask without disabling fixture provenance.
        )
        export = collector.run(max_polls=1)
        assert export["counts"]["EURUSD"]["valid"] == 1
        assert export["counts"]["XAUUSD"]["valid"] == 0
    finally:
        store.close()


def test_mt5_profile_conversion_retains_raw_and_dedup_survives_profile_update(
    tmp_path, clock_profile_factory
):
    reader = FakeReader(tmp_path / "terminal/terminal64.exe", lambda: NOW)
    raw = int((NOW + timedelta(hours=3)).timestamp())
    reader.quote_overrides.update(time=raw, time_msc=raw * 1000)
    p = clock_profile_factory(
        semantics="broker_wall_epoch",
        periods=[
            dict(start="2024-01-01T00:00:00Z", end="2025-01-01T00:00:00Z", offset_seconds=10800)
        ],
    )
    feed = MT5Feed(
        reader,
        FeedConfig(),
        terminal_path=reader.path,
        login=str(reader.login),
        server=reader.server,
        clock=lambda: NOW,
        clock_profile=p,
    )
    feed.connect()
    row, native = feed.quote("EURUSD")
    assert row.source_at == NOW and native["time"] == raw
    updated = row.model_copy(
        update={
            "clock_stamp": row.clock_stamp.model_copy(
                update={"profile_id": "other.v2", "profile_digest": "b" * 64}
            )
        }
    )
    identity = feed.verify().fingerprint
    assert record_id(row, identity) == record_id(updated, identity)
    store = FeedStore(tmp_path, feed.config, code_version="fixture")
    try:
        session, _ = store.session(identity, NOW, synthetic=True)
        store.commit(session, [row], [native], received_at=NOW, warnings=[])
        before = store.last_commit()
        assert (
            store.commit(session, [updated], [native], received_at=NOW, warnings=[])["duplicates"]
            == 1
        )
        for path, digest in before["files"].items():
            from tb.ingest.history.core import sha256_file

            assert sha256_file(tmp_path / path) == digest
    finally:
        store.close()
    feed.clock_profile = p.model_copy(update={"state": ClockState.PROVISIONAL})
    with pytest.raises(FeedUnavailable, match="not_verified"):
        feed.quote("EURUSD")
