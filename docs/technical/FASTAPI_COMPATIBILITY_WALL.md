<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-17 -->

# FastAPI 0.137+ Routing Introspection Compatibility Wall

This document defines the technical constraints, impact, and exit criteria for the FastAPI version lock (`fastapi<0.137.0`) in the GoodQ4All baseline environment.

## Background & Technical Seam

In June 2026, CI pipeline verification failed after upgrading FastAPI past `0.136.x`. The failure occurred in the route introspection suite, specifically:
`tests/unit/test_api_main_legacy_prune_truth.py`

This test suite asserts that retired legacy endpoints are completely pruned from the application, and that all active canonical routes (like `/api/status`, `/api/health/summary`, etc.) are successfully registered. It performs this check by reading:
```python
paths = {route.path for route in api_main.app.routes if hasattr(route, "path")}
```

### The Breaking Change in FastAPI 0.137+

Starting with version `0.137.0`, FastAPI altered how `app.include_router(...)` handles route inclusion. 
- **Previous Behavior**: Included routers immediately flattened their routes directly into the main `app.routes` list as `APIRoute` instances. Introspection code could easily check `route.path` on all registered routes.
- **New Behavior**: Included routers are wrapped in opaque `_IncludedRouter` objects inside `app.routes`. These wrapper objects:
  - Do **not** have a `.path` attribute directly on them.
  - Do **not** expose their child routes through a public `.routes` API.
  - Encapsulate the sub-routes internally, hiding them from simple direct iteration over `app.routes`.

Because of this wrapping, our route verification tests could no longer locate active endpoints nested under the included routers (e.g. `/api/status` or `/api/engines`), causing assertion failures:
`AssertionError: assert surviving_paths.issubset(paths)` (where `paths` was empty or only contained unnested endpoints like mounted static directories).

## Strategic Resolution

To maintain release stability and robust verification of pruned routes, we have:
1. Pinned `fastapi<0.137.0` in `environment.yml` and lockfiles to preserve flat route iteration.
2. Added defense-in-depth `hasattr(route, "path")` guards to ensure the tests remain robust against other routing object types.

This is an intentional compatibility wall to prevent silent route list opacity, not a permanent limitation.

## Exit Criteria for Upgrading FastAPI

To remove the `fastapi<0.137.0` pin in the future, the following conditions must be met:

1. **Introspection Independence**: Route discovery in unit tests must no longer assume a flat `app.routes` list structure or rely on private properties of `_IncludedRouter`.
2. **Recursive Traversal or OpenAPI Extraction**:
   - The test suite must be updated to recursively traverse `_IncludedRouter` instances if they exist, or
   - The test suite must retrieve the registered route surfaces via FastAPI's OpenAPI generator (e.g., calling `app.openapi()` and parsing the path keys).
3. **Validation Verification**: Route tests must continue to successfully detect missing, renamed, or legacy endpoints with the new traversal mechanism.
4. **CI Lane Verification**: At least one CI lane in the matrix must be run with a FastAPI version >= `0.137.0` to verify compatibility before the baseline pins are updated.
