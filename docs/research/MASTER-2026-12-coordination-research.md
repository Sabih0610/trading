# December coordination research

2026-11-05. The owner-approved [swing research](../../reports/reviews/swing-research-2026-11-05.md) and [master](../../prompts/MASTER-2026-12.md) supply scope. Trackagents research their implementation topics independently before coding.

| Question | Decision | Reason |
|---|---|---|
| Branch conflicts | Separate M/N/O worktrees and rootliving branch | Match master's file ownership and preserve coworker work. |
| Resource contention | Root serializes fullgates/heavybuilds and avoids focused tests duringfullsuites | Host16GB and prior documented cold-start timing contention. |
| P data access | Start onlyafterallMNOmerges, stop PartA until APPROVED onmain | Avoid leakage/retuning and preserve independent review. |
| Continuation | New quiet15minute heartbeat, actualstate handoffs, delete atmastercompletion | Ownerauthorizedunattendedwork plus persistentcontinuation. |

[Official scheduled-task documentation](https://learn.chatgpt.com/docs/automations?surface=app), accessed2026-11-05, was checked through OpenAI Docs for the existing-session recurring follow-up mechanism. It states local scheduled tasks require the computer/app running. The available automationtool supplies the heartbeat schema; no API/client/runtime change is introduced. Previous [living workflow research](MASTER-2026-11-final-living-research.md) supplies unchanged Git/JSON handling.
