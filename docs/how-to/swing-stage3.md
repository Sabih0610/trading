# Reviewing the swing registration

PartA contains a research specification only. It has no runnable genuine P command.
Read [the registration](../../reports/stage3/P11p-preregistration.md) and its
[phase report](../../reports/phases/P11p.md). Claude writes the independent verdict
to reports/reviews/P11p-prereg-review.md on main.

From the checkout root in PowerShell, inspect the public evidence:
```powershell
git fetch origin main
git show origin/main:reports/reviews/P11p-prereg-review.md
Get-FileHash -Algorithm SHA256 -LiteralPath './reports/stage3/P11p-preregistration.md'
```

Missing review, nonapproval or a different registration identity keeps genuine
access disabled. No registry/quality/price read is a troubleshooting step before
approval. After approval all PartB code/config must be tested, frozen and published
before data access. A future approved CLI will be documented here only when built.
A result, even pass, never enables paper trading, providers or orders.
