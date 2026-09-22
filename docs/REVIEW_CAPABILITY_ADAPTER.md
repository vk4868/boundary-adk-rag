# ADK environment parity correction

Root traced the native and initial deployed HTTP failures to ADK 2.9.2's environment-dependent Gemini capability selection. With `GOOGLE_GENAI_USE_VERTEXAI=true`, ADK advertised combined schema/tool support, retained JSON response mode and omitted the formatter tool. The workflow's forced function calls then produced provider HTTP 400. Local dotenv settings configured the actual Vertex client but did not set that process variable, so the earlier local run took a different ADK formatting path.

Sol added `GovernedGemini` to explicitly select the formatter-tool path. Forced researcher calls use text/plain and clear both schema fields. The actual Vertex client/project/location remain unchanged, and the separate reviewer keeps tool-free JSON output. Retrieval, base prompts and the final release gate were not changed.

Terra independently reviewed the adapter and actual ADK request-processor tests. Ten focused tests passed in normal, clean Vertex-true and clean Vertex-false processes. These cover HTTP/native variants, formatter injection, forced tool mode, researcher MIME/schema fields and separate reviewer configuration. Root independently ran the full final offline suite: 88 tests plus 12 subtests passed in 1.26 seconds. No model calls occurred in these tests.

Outcome: offline environment-parity review passed; a new immutable image and restarted processes were required for subsequent live evidence. The preserved v3 development metrics predate this adapter. Final native and deployed acceptance results must be reported separately, retaining the original integration failures.
