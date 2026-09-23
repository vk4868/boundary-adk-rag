# Native quality review

A reviewer-only agent (`/root/astra_orchestrator/review_ui`, configured GPT-5.6 Terra) assessed the saved native ADK evaluation outputs against the fixed corpus. This is an agent source assessment, not human approval.

The native run covered 3 development cases and 4 turns. All three native case records report `final_eval_status` passed and a `tool_trajectory_avg_score` of 1.0. That metric checks the configured tool trajectory and does not measure factual support, completeness, or semantic correctness.

The separate source assessment found 3 supported answer turns and 1 withheld answerable follow-up. At case level, 2 of 3 cases completed with source-supported answers; the remaining case's setup answer was supported, but its requested MCC comparison was rejected with no claims or citations and therefore does not pass semantic completion.

The native summary hash was `dcb343fc04f693782bdf8645b48913a3e7206aa66530d6b3071ae65f154ba112`; the native evaluation-set hash was `5b1b848516d3919288c9790cb050157c2e188e8919d449a90c9eba1d4d69c496`; the metric-config hash was `777cc1f8a1d873dfb47ebb4be0dd0515507d3239a4b8ef8715211f13c40d325d`; the frozen runtime hash was `8ca895bc06b2fd3b978a8ebf1bb5fd672c7fbb3dcdb030ea3b238b9db9044c17`; and the fixed-index hash was `4518de9adb0d63f4217eeb52e917671ad802ca78dd6952264aa96cc1f8ac1cee`.

The private assessment under `work/native-quality-v3.semantic-review.json` retains per-turn evidence references and artifact hashes with restricted permissions. This public record intentionally excludes prompts, responses, source passages, session data, and tool traces.
