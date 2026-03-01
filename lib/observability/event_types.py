from __future__ import annotations

from typing import Literal


EventName = Literal[
    "step_start",
    "step_progress",
    "step_end",
    "step_error",
    "heartbeat",
]


STEP_START: EventName = "step_start"
STEP_PROGRESS: EventName = "step_progress"
STEP_END: EventName = "step_end"
STEP_ERROR: EventName = "step_error"
HEARTBEAT: EventName = "heartbeat"

