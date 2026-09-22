# Working-Rules Review

Reviewer-only review completed on 2026-09-22.

## Scope

- `AGENTS.md`
- Current configuration, request/session service, ADK pipeline, deterministic gate, audit logger, corpus-index metadata, deployment instructions, and existing review evidence.

## Result

`AGENTS.md` passes this review. It accurately separates user-authorized requirements from current implementation choices and done criteria. It preserves the US$10 total Google-service ceiling, 10-hour target, source privacy, private deployment boundary, no-publication restriction, root-owned paid/cloud work, and no-new-approval-gate rule for already-authorized reversible work.

The document’s implementation claims match the reviewed code: server-assigned role and authenticated sessions, current-invocation evidence requirements, researcher/reviewer/deterministic-gate sequencing, audit fail-closed behavior, private index constraints, response-status labeling, bounded calls/timeouts, and the custom versus native evaluation distinctions.

The generation model is correctly described as a configured Vertex target with live generation acceptance recorded separately. The reviewed index descriptor records the separate Vertex embedding snapshot configuration. This review does not claim a live model, deployment, semantic-evaluation, or final-acceptance result.
