# Run Windows offline validation

Run from a dedicated checkout with no private .env. This checks owned software mechanics only.
It runs locked dependencies, lint/format/types, the entire default offline suite, legacy paper smoke
and all fourteen finite owned studies. It does not connect providers or place orders.

```powershell
pwsh -NoProfile -File '.\scripts\check-offline.ps1'
```

If uv is outside PATH, supply its verified local location with `-Uv 'path with spaces\uv.exe'`.
Optional `-TemporaryRoot` must name an existing folder. Outputs use a new tb-offline-<random> child;
the script prints that location on success. No source data or credentials are copied there, no
artifacts are uploaded, and no recursive deletion occurs. Remove disposable owned outputs manually
after review. Registry/dependency setup uses the network; Python checks subsequently enable a socket
accident guard and uv offline mode. Existing live tests remain deselected by project configuration.

Any failed native command stops the script with a failure. Windows tests inject separate lint,
formatting, type, pytest and smoke failures to verify propagation. A missing or corrupt journal is
refused; do not edit manifests or regenerate existing evidence to force success. Source changes use
a new owned-study namespace. Prior P11b.2a evidence requires its original pinned source for replay.

## Hosted status

The workflow is local only until reviewed and pushed with separate owner authorization. Its job
requires repository variable OFFLINE_CI_APPROVED_FREE_RUNNER equal to true and a public repository.
The owner must first verify Actions policies/eligibility and free standard Windows runner use. Do
not enable paid/larger runners or change branch protection as part of this milestone. No hosted pass
is claimed. A skipped gated job is not a successful validation run.

Actions are pinned to reviewed SHA revisions; checkout credentials are not persisted, permissions
are contents read, caching/uploads disabled and job timeout twenty minutes. Installation pins uv
0.13.5 and Python 3.12.11. Recheck upstream security/compatibility before changing pins.

See [phase report](../../reports/phases/P11b.2a.1.md), [research](../research/P11b.2a.1-research.md)
and [future integration contract](../specifications/P11b.2b-genuine-input-contract.md).
