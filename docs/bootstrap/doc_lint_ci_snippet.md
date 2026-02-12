# Doc Lint CI Snippet

<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

Use this as a minimal GitHub Actions step to enforce documentation drift checks.

```yaml
- name: Lint documentation drift
  shell: bash
  run: |
    python scripts/docs/doc_drift_lint.py
```

Optional full job example:

```yaml
name: docs-lint
on:
  pull_request:
    paths:
      - "docs/**"
      - "README*.md"
      - "scripts/docs/doc_drift_lint.py"

jobs:
  docs-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Lint documentation drift
        run: python scripts/docs/doc_drift_lint.py
```
