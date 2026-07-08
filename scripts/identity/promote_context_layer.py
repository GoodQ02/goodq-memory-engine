"""
GoodQ4All — Phase 5B: Context Layer Promotion (Holiday / Place nodes)
======================================================================
STATUS: NOT YET IMPLEMENTED — STUB ONLY.

This phase adds Holiday and Place nodes to the knowledge graph after
the person identity layer (Phase 5A) has been validated.

Separation rationale:
  People first. Then context. The person identity layer must be stable
  and validated before adding event/place context to avoid mixing
  identity and context concerns during the labeling process.

Planned implementation:
  - OCR date overlay mining: extract date/holiday patterns from image_ocr
    UCF frames (e.g., "DEC 25 1990" → Christmas 1990 node).
  - Transcript keyword mining: detect holiday/location references using
    a private places.yaml and holidays.yaml (user-curated, gitignored).
  - Scene-level Holiday and Place node creation with person cross-links.
  - Same backup + dry-run + confirm pattern as Phase 5A.
  - Separate config flag: context_enrichment.enabled: false.

Usage (when implemented):
    conda run -n goodq_core python scripts/identity/promote_context_layer.py \\
        --epoch-id <epoch_id> --dry-run
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    log.error(
        "promote_context_layer.py is not yet implemented. "
        "Complete and validate Phase 5A (person identity nodes) first. "
        "See script docstring for planned implementation details."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
