# P11j Wave 1 research

Research accessed 2026-11-03 before implementation; all validation is owned fixtures.
Pinned versions remain Python 3.12, pytest 9.1.1 and Hypothesis 6.170.5.

| Question | Options | Decision |
|---|---|---|
| Quantity rounding | Ambient half-even / directed positive division | ROUND_DOWN in local Decimal contexts; step flooring also uses directed division, including null-filter quantity precision. No fabricated exchange filter. |
| Cold query deadline | Relax assertions / disable deadline / untimed warm-up | Warm exact feature/resample paths in module fixtures; observed loaded examples still reached1.108s. Apply an explicit2s deadline only to those two properties as authorized, preserving every assertion/example count and all other default deadlines. |
| Six-hour hang evidence | Fail tests by timer / built-in stack dump | pytest faulthandler_timeout=600 dumps stacks without failing or skipping; add explicit missing subprocess bounds. |
| Synthetic chart exemption | Trust manifest / uniform holdout | Every chart mode refuses 2025+ manifest/actual timestamps, including beyond the displayed page. |
| Skill provenance | Floating HEAD / reviewed SHA | Reuse the two documented audited commits, verify detached checkout, refuse dirty cache. |
| Missing feature logging | Values / repeated messages / names once | Names/reasons only, once per process; stderr protects JSON stdout; private dotenv not opened merely to initialize logs. |

Primary sources:
- [Python Decimal](https://docs.python.org/3.12/library/decimal.html), directed rounding and local contexts.
- [pytest fault handler](https://docs.pytest.org/en/stable/how-to/failures.html), diagnostic timeout.
- [pytest fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html), module-scoped setup outside test bodies.
- [Hypothesis settings](https://hypothesis.readthedocs.io/en/latest/settings.html), example deadline semantics.
- [Git checkout](https://git-scm.com/docs/git-checkout), detached commit identity; existing reviewed hashes remain documented in docs/skills.md.

Limitations: undefined exchange filters still are not live exchange qualification; directed research precision is no replacement for verified venue metadata. Wave 2 fill/label semantics remain deferred until F and G Part B merge.
