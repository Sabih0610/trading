# Record documented data-rights approvals

The current Twelve Data policy has no affirmative genuine approvals. Support confirmation is
pending. This workflow validates a human's documented proposal offline; it never contacts a
provider, loads credentials, grants rights from a support request or starts market collection.
No genuine policy was applied in P11b.0.1. Existing records must not be deleted automatically.

## Prepare a proposal for review

From the repository root in PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path '.\work\rights' | Out-Null
Copy-Item -LiteralPath '.\config\data_rights_review.example.yaml' -Destination '.\work\rights\proposal.yaml'
```

The template is deliberately unapproved. Resolve each relevant usage independently using current
provider documentation or an actual written response. A request email/ticket is `request_pending`,
which cannot approve use even if someone checks `approved`. Do not infer Basic storage, derived,
AI or training rights from endpoint access or higher-plan marketing.

Record exact policy ID/new version, provider `twelve_data`, both instruments, review time and the
existing public source/account fingerprint. Obtain the fingerprint from prior local source
metadata; never place the API key in the proposal or a command. For every approved usage provide:

- Confirmed status, affirmative `approved: true` and the human reviewer in `approved_by`.
- A concrete documentary citation and `evidence_kind: provider_terms` or `provider_confirmation`.
- A project-relative file under `work/rights/` in `evidence_artifact`, and its exact SHA256 in
  `evidence_sha256`. Keep the original source/date/context and applicable account/plan/instruments.
- Finite UTC `expires_at`, separate from the data retention duration.
- Positive `permitted_retention_seconds` for raw cache, historical and derived storage.

Documentary files stay ignored/local. They must contain no key or token. Compute a document hash:

```powershell
Get-FileHash -LiteralPath '.\work\rights\provider-confirmation.txt' -Algorithm SHA256
```

Retrieval, raw cache, historical storage, derived storage and persistent collection must each pass
for a genuine shadow study. Private raw display, commercial use, AI analysis and ML training are
separate permissions; leave them closed unless specifically documented and approved. This phase
uses none of those extra capabilities.

## Check without applying

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.rights_review --proposal '.\work\rights\proposal.yaml'
```

A passing check establishes structural completeness and artifact integrity only. A human still
must confirm that the document actually grants this use. Unknown scope, missing approvals,
request-pending evidence, missing/changed documents, expired permissions, absent reviewer or
retention duration refuses. Input files are bounded; `.env` is not a proposal or evidence file.
No API key is loaded, and the active policy/source records are unchanged by a check.

## Apply only after the owner has reviewed the evidence

The following is a future explicit owner action, not a command to run under the current policy:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.rights_review --proposal '.\work\rights\proposal.yaml' --apply
```

It atomically installs only the public approval policy and requires a new version. It does not
start acquisition, unlock history, rewrite data provenance or enable execution. A changed rights
hash invalidates old study pins; create a separately reviewed study, never mutate the old journal.
Do not put confidential provider correspondence or credentials into Git. Review a public policy
diff before committing it; source evidence and keys remain ignored/local.

Before any future supervised run, require adequate actual entitlements, clocks, quota and a lawful
retention/expiry procedure for cache, originals, derivatives and backups. The finite collector and
consumer refuse a run longer than the recorded retention window minus five minutes. No automated
purge is installed; if prior records require remediation, the owner must approve a specific plan.
See [conditional trial](../P11b.0.1-supervised-trial-plan.md) and [pending](../pending.md).
