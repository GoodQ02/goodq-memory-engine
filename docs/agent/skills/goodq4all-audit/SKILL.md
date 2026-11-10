---
name: goodq4all-audit
description: Run an explicitly requested external LLM code audit of GoodQ using its existing audit script.
---

# External GoodQ code audit

This is an optional cloud audit, not a startup check or ordinary code-review
requirement. Use local source inspection and deterministic checks first.

`scripts/audit_llm.py` bundles source/configuration for a Vertex AI request.
Before execution, inspect its current bundle selection, model/region, output
path and credential behavior. Confirm that the task authorizes sending that
exact content to the external service and charging the selected project. Exclude
secrets and personal data; if the script cannot honor the approved scope, stop
before sending. Do not enable APIs, change authentication/billing defaults or
install dependencies as an implicit prerequisite.

Use an existing appropriate environment and explicit approved project/region
arguments supported by the script. Resolve current provider/model availability
from official documentation when needed; historical model names and quota
examples are not present configuration. Keep generated reports in task evidence.

Treat model findings as leads. Check the actual code path and reproduce material
claims before proposing fixes. Report validated findings and material uncertainty
with locations, evidence and impact. Apply `AGENTS.md` and relevant contracts;
do not turn generic audit advice into unconditional code rewrites.
