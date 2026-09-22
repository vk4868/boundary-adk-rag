# Offline Test Boundary Review

Reviewer-only audit completed on 2026-09-22.

## Executed check

```text
env -i PATH=/usr/bin:/bin .venv/bin/python -m pytest -q \
  tests/test_service_boundaries.py tests/test_native_eval.py

11 passed
```

Only the named test files above were executed in this review. The aggregate Python suite and Node suite were not rerun by this reviewer.

## Isolation evidence

`tests/test_service_boundaries.py` builds settings explicitly with `_env_file=None`. Its synthetic model-ready fixture replaces index loading with a local no-op and replaces ordinary agent construction with an assertion failure. The stale-response check supplies a fake in-memory runner. Its `TestClient` check exercises the FastAPI app in process with a synthetic disabled-model configuration; it does not start the root server or send a network request.

`tests/test_native_eval.py` reads the local native eval-set and config files, then evaluates synthetic invocation objects with the ADK trajectory metric. It does not invoke `adk eval`, an API endpoint, or a model.

No `.env` file, cloud credential, model call, root server, or native ADK CLI run was used by this review.

## Final frozen-revision offline run

After the final ranking correction was reviewed and runtime frozen, Astra independently ran `.venv/bin/python -m pytest -q`: **83 tests and 12 subtests passed in 1.04 seconds**. The Node response-validator suite also passed. Warnings were confined to the pinned SDK's deprecations/experimental schema feature and test-client deprecations. Tests use synthetic/mocked provider execution and isolated settings; this run made no paid calls and did not change the runtime. Live development, native trajectory and deployed acceptance remain separate evidence categories.
