from __future__ import annotations

"""
Canonical sensitive event schemas (v1).

This module defines structure only. It must not:
- ingest or parse raw content
- log raw message text / health measurements / wearable media
- imply vault content exists (audit absence is not evidence)

Raw content is vault-only by default; public conduits must store tokens only.
"""

from typing import List, Literal, TypedDict

SchemaVersion = Literal[1]
VaultRefToken = str

MessagePlatform = Literal["imessage", "sms", "fb", "ig", "whatsapp", "signal", "telegram", "other"]
MessageDirection = Literal["in", "out"]

HealthSource = Literal["apple_health", "google_fit", "garmin", "oura", "other"]
HealthCategory = Literal["sleep", "activity", "heart", "nutrition", "mood", "other"]

WearableDevice = Literal["rayban_meta", "other"]
WearableModality = Literal["image", "video", "audio", "sensor"]


class _CanonicalMessageEventRequired(TypedDict):
    schema_version: SchemaVersion
    message_id: str
    thread_id: str
    platform: MessagePlatform
    timestamp_utc: str
    direction: MessageDirection
    participant_ids: List[str]
    content_ref: VaultRefToken


class CanonicalMessageEvent(_CanonicalMessageEventRequired, total=False):
    entity_ids: List[str]
    sentiment_summary: str
    topic_tags: List[str]


class _CanonicalHealthEventRequired(TypedDict):
    schema_version: SchemaVersion
    event_id: str
    source: HealthSource
    timestamp_utc: str
    category: HealthCategory
    measurement_type: str
    value_ref: VaultRefToken


class CanonicalHealthEvent(_CanonicalHealthEventRequired, total=False):
    start_ts_utc: str
    end_ts_utc: str
    daily_aggregate_bucket: str
    trend_delta: float
    anomaly_flags: List[str]


class _CanonicalWearableEventRequired(TypedDict):
    schema_version: SchemaVersion
    capture_id: str
    device: WearableDevice
    timestamp_utc: str
    modality: WearableModality
    media_ref: VaultRefToken


class CanonicalWearableEvent(_CanonicalWearableEventRequired, total=False):
    scene_id: str
    entity_ids: List[str]
    transcription_ref: VaultRefToken
    summary_ref: VaultRefToken

