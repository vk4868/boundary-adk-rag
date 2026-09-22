# Working-Rules Review

Reviewer-only review completed on 2026-09-22.

## Scope

- `AGENTS.md`
- Current configuration, request/session service, ADK pipeline, deterministic gate, audit logger, corpus-index metadata, deployment instructions, and existing review evidence.

## Result

At that review checkpoint, `AGENTS.md` accurately separated user-authorized requirements from implementation choices and done criteria, including the then-current no-publication restriction. The user subsequently authorized GitHub publication of the source code and three PDFs. That later authorization supersedes only the repository/PDF publication restriction; the Google-service ceiling, private runtime/deployment boundary, root-owned paid/cloud work and protection of credentials, indexes, logs and raw evaluation artifacts remain in force.

The document’s implementation claims match the reviewed code: server-assigned role and authenticated sessions, current-invocation evidence requirements, researcher/reviewer/deterministic-gate sequencing, audit fail-closed behavior, private index constraints, response-status labeling, bounded calls/timeouts, and the custom versus native evaluation distinctions.

The generation model is correctly described as a configured Vertex target with live generation acceptance recorded separately. The reviewed index descriptor records the separate Vertex embedding snapshot configuration. This review does not claim a live model, deployment, semantic-evaluation, or final-acceptance result.
