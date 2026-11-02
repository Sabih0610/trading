# Private P11e quality table template

This is a blank metadata template. Generate the populated version only under the
ignored `reports/data_quality/` directory. Do not paste genuine values into Git.
Use one row for every approved symbol/year, including unavailable years, and one
source-specific row if both primary and backup exist.

| Symbol | UTC year | Source | Price side | Status | Quality score | Missing open minutes | Duplicates/revisions | Gap reason | Private quality path |
|---|---|---|---|---|---|---|---|---|---|
| `<symbol>` | `<year>` | `<provider>` | `<side>` | `<status>` | `<private>` | `<private>` | `<private>` | `<reason>` | `<ignored local path>` |


## Private clock-fix comparison (blank template)

Keep populated values in ignored reports/data_quality/, never in this document.

| Symbol | Year | Old duplicates_removed | New duplicates_removed | Verified provider duplicate hours | Weeks checked | Weeks flagged | Private details |
|---|---|---|---|---|---|---|---|
| <symbol> | <year> | <count> | <count> | <count> | <count> | <count> | <local path> |

The private detail table lists each week's expected/observed UTC open, signed
minute offset or missing-week status. Record quarantined source days and reasons.
Do not shift observations to fit weekly opens or infer spread from bid-only data.
