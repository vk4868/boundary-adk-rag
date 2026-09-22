# Bounded formatter-read repair review

Sol implemented the researcher callback repair in `app/agents.py` and per-invocation repair state in `app/tools.py`. A reviewer-only GPT-5.6 Terra agent inspected the implementation and `tests/test_formatter_read_repair.py`, then independently ran all seven focused tests successfully. Sol reported the full offline suite at 80 tests plus 12 subtests and the Node response-validator suite passing. No model calls occurred in these checks.

The repair intercepts structured finalization once for unread citation IDs that were issued during this invocation and pass the source ACL. It requests one actual read of exactly the missing set, reserving three model slots for read, revised finalization and review. It never inserts read IDs itself. Tests cover the actual ADK formatter callback, successful seven-call path, wrong/subset/failed read, late budget, invented/unauthorized IDs and per-turn reset. Ineligible or unsuccessful repair remains subject to the unchanged final gate.

An initial review incorrectly interpreted “current-search” as “latest search.” Root clarified the intended boundary: all issued IDs in the current invocation are eligible, because comparisons may need several searches. The briefly added latest-search restriction was reverted; misleading strings were corrected. The final regression proves that an earlier search in the same invocation can be repaired, while prior-invocation IDs cannot qualify. The reviewer withdrew the functional finding and approved the final implementation.

AGENTS, architecture and learning-guide descriptions were also reviewed for fidelity. Outcome: offline review passed and the runtime was released for root's separate live evaluation. This review does not establish live repair effectiveness or semantic correctness; those results must retain their own run IDs and denominators.

## Separate selected live check

`work/dev-repair-smoke-v1.json` preserves three final cases, five planned/dispatched turns, four saved responses and one automated final pass. A separate Terra source assessment in private `work/dev-repair-smoke-v1.semantic-review.json` agrees with the one final pass: dev-12 correctly answers the playoff distinction using USIG pages 3 and 10. Its setup remains supported but incomplete. Dev-13's setup passes, but its final comparison is withheld and does not complete the task; dev-11 is unavailable after an HTTP/SDK error.

The dev-12 trace demonstrates an actual formatter→read→formatter recovery. That is evidence that this repair path executed, not that it resolves every missing citation or semantic omission. All failures and the incomplete setup are retained; this selected check is not a full development or final acceptance run.
