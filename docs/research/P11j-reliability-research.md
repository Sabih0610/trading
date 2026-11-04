# P11j Wave 1 reliability follow-up research

Read the two reviewer follow-ups on 2026-11-04 before changing tests. Python remains
3.12, pytest 9.1.1 and Hypothesis 6.170.5. Every existing assertion and generated
input range is retained. No production behavior changes.

| Question | Options compared | Decision and reason |
|---|---|---|
| Child cold startup under load | One larger elapsed timeout; explicit readiness and separate operation bound | The child signals only after imports, package loading and store reopening/replay. The parent acknowledges through stdin before the original event and fault hook execute. Cold startup gets 120s; acknowledged operation gets 60s. Neither depends on an assumed startup delay. |
| Child failure cleanup | Unbounded pipe reads; bounded communicate plus kill/reap | Poll the temporary readiness marker with a monotonic 120s deadline and early-exit detection. Every communicate has a timeout, including 10s cleanup. Kill a remaining child in finally; retain stderr for the unchanged exit-code assertion. |
| Cold datetime property call | Disable deadlines globally; relax assertion; untimed warm-up and local finite deadline | Use the approved J1 pattern: module fixture warms the exact conversion path, and only this property gets 2s. The 1970-2100 UTC range and exact equality assertion are unchanged. |
| Full-suite concurrency | Another simultaneous heavy run; queue one clean gate | Queue behind G on the 16GB host. Focused checks do not count as a full-gate pass. |

Primary sources, accessed 2026-11-04:

- [Python 3.12 subprocess](https://docs.python.org/3.12/library/subprocess.html#subprocess.Popen.communicate): communicate timeouts do not terminate Popen children automatically; kill and complete communication for cleanup. Initial OS process creation itself is not interruptible by the subprocess timeout.
- [Hypothesis API settings](https://hypothesis.readthedocs.io/en/latest/reference/api.html#hypothesis.settings.deadline): deadlines time individual examples; use a local setting when wall time is affected by first-use or scheduling overhead.
- [pytest fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html): module-scoped setup executes outside the property body and is reused by module tests.

Limitations: finite timeout failures still fail the test. This improves coordination;
it does not classify unexplained future failures as harmless or retry them into a pass.
Review direction comes from P11i-1 and the P11j review, not a new performance standard.
