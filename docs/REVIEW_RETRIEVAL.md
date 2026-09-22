# Constraint-preserving retrieval review

Sol implemented a bounded retrieval change after preserved live diagnostics showed two distinct failures: the correct pitch page ranked first but its prefix preview hid the relevant section, and a junior-rule search paraphrase omitted the requested format and player-count attribute.

The change preserves the current user question alongside the bounded model refinement, selects a query-focused 700-character preview, and combines normalized BM25 (65%) with normalized cosine similarity (35%) over authorized candidate pages. It uses one real Vertex query embedding and the unchanged fixed index. The weights are development choices, not proven optimal. Model refinements default to 1,200 characters; the combined query defaults to 7,500 with a supported maximum of 10,000. Overflow and embedding truncation fail explicitly.

A reviewer-only Terra agent inspected query propagation, installed ADK current-message behavior, ACL ordering, score labeling, bounds and source privacy. The reviewer found that min–max normalization could promote a negative cosine with no lexical match into a positive hybrid score. Sol added a raw-score admissibility floor and a regression; Terra re-reviewed the fix. Astra independently inspected the final implementation and reproduced the full offline suite.

Final result at this checkpoint: six retrieval regressions passed and **58 total Python tests passed**. The index SHA-256 remained `4518de9adb0d63f4217eeb52e917671ad802ca78dd6952264aa96cc1f8ac1cee`. No reviewer made a provider, endpoint or native-evaluation call. The configured generation model was unchanged.

This establishes offline boundary behavior. It does not prove that the model chooses every relevant page, extracts the correct table row, or answers every requested attribute. The final citation gate remains authoritative, and source-based assessment of the subsequent live retry is separate. Existing baseline and diagnostic responses were preserved.

## Final narrow ranking correction

A later real dev-09 trace showed source-name and embedding-wrapper words dominating global BM25 across two selected documents. The final correction keeps the exact combined Vertex query and fixed vectors unchanged, while supplying a separate clean lexical question/refinement. Under explicit source filtering, metadata-derived source identity terms are removed only from the lexical/snippet channel; substantive qualifiers remain. No source/page answer tables or stemming rules were added.

A reviewer-only Terra pass found no ACL, scope or additional-provider-call regression and independently ran eight focused retrieval tests successfully. Synthetic tests cover cross-source title-page distortion and preservation of Under-12 format qualifiers. Sol reported the full offline suite at 83 tests plus 12 subtests, with Node validation and compilation passing. The final runtime freeze was released for root's full live validation; offline ranking improvements are not a substitute for those results.
