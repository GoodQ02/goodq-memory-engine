from fastapi import APIRouter

# Retired compatibility placeholder.
# The old /runs/{run_id} summary surface is no longer mounted because its
# backing summary module is gone and should not be silently recreated.
router = APIRouter()
