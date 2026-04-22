"""
Sensitive Source Wiring Pack v1: UI-safe reserved conduits (derived-only; empty by default).

Non-negotiable:
- Never store raw message text, raw health measurements (per-record), or raw wearable media here.
- Never store absolute filesystem paths here (vault references are tokens only).

These tables are intentionally empty until a future, explicitly approved ingestion/parsing job
populates them from a local vault.
"""

from __future__ import annotations

import sqlite3

_SCHEMA_SQL = """
-- Messages (UI-safe)
CREATE TABLE IF NOT EXISTS thread_index_public (
  thread_id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  first_ts_utc TEXT,
  last_ts_utc TEXT,
  participant_count INTEGER NOT NULL,
  participant_ids_json TEXT,
  message_count INTEGER NOT NULL,
  last_direction TEXT,
  last_message_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_tip_platform ON thread_index_public(platform);
CREATE INDEX IF NOT EXISTS idx_tip_last_ts ON thread_index_public(last_ts_utc);

CREATE TABLE IF NOT EXISTS message_activity_daily_public (
  day_utc TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  platform TEXT,
  in_count INTEGER NOT NULL,
  out_count INTEGER NOT NULL,
  total_count INTEGER NOT NULL,
  first_ts_utc TEXT,
  last_ts_utc TEXT,
  PRIMARY KEY (day_utc, thread_id)
);
CREATE INDEX IF NOT EXISTS idx_madp_day ON message_activity_daily_public(day_utc);
CREATE INDEX IF NOT EXISTS idx_madp_thread ON message_activity_daily_public(thread_id);

CREATE TABLE IF NOT EXISTS entity_thread_mentions_public (
  thread_id TEXT NOT NULL,
  platform TEXT,
  entity_id TEXT NOT NULL,
  mention_count INTEGER NOT NULL,
  first_ts_utc TEXT,
  last_ts_utc TEXT,
  PRIMARY KEY (thread_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_etmp_entity ON entity_thread_mentions_public(entity_id);

-- Health (UI-safe; aggregated/flags only)
CREATE TABLE IF NOT EXISTS health_activity_daily_public (
  day_utc TEXT NOT NULL,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  measurement_type TEXT NOT NULL,
  daily_aggregate_bucket TEXT,
  record_count INTEGER NOT NULL,
  PRIMARY KEY (day_utc, source, category, measurement_type)
);
CREATE INDEX IF NOT EXISTS idx_hadp_day ON health_activity_daily_public(day_utc);
CREATE INDEX IF NOT EXISTS idx_hadp_type ON health_activity_daily_public(measurement_type);

CREATE TABLE IF NOT EXISTS health_trends_public (
  day_utc TEXT NOT NULL,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  measurement_type TEXT NOT NULL,
  trend_window_days INTEGER,
  trend_delta REAL,
  trend_label TEXT,
  PRIMARY KEY (day_utc, source, category, measurement_type)
);
CREATE INDEX IF NOT EXISTS idx_htp_type ON health_trends_public(measurement_type);

CREATE TABLE IF NOT EXISTS health_anomalies_public (
  day_utc TEXT NOT NULL,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  measurement_type TEXT NOT NULL,
  anomaly_flags_json TEXT NOT NULL,
  severity TEXT,
  note TEXT,
  PRIMARY KEY (day_utc, source, category, measurement_type)
);
CREATE INDEX IF NOT EXISTS idx_hap_type ON health_anomalies_public(measurement_type);

-- Wearables (UI-safe; token refs only)
CREATE TABLE IF NOT EXISTS wearable_capture_index_public (
  capture_id TEXT PRIMARY KEY,
  device TEXT NOT NULL,
  timestamp_utc TEXT NOT NULL,
  modality TEXT NOT NULL,
  media_ref TEXT NOT NULL,
  scene_id TEXT,
  entity_ids_json TEXT,
  transcription_ref TEXT,
  summary_ref TEXT,
  derived_ready INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wcip_device ON wearable_capture_index_public(device);
CREATE INDEX IF NOT EXISTS idx_wcip_ts ON wearable_capture_index_public(timestamp_utc);

CREATE TABLE IF NOT EXISTS wearable_timeline_public (
  day_utc TEXT NOT NULL,
  device TEXT NOT NULL,
  modality TEXT NOT NULL,
  capture_count INTEGER NOT NULL,
  first_ts_utc TEXT,
  last_ts_utc TEXT,
  PRIMARY KEY (day_utc, device, modality)
);
CREATE INDEX IF NOT EXISTS idx_wtp_day ON wearable_timeline_public(day_utc);

CREATE TABLE IF NOT EXISTS wearable_entity_mentions_public (
  entity_id TEXT NOT NULL,
  device TEXT,
  modality TEXT,
  mention_count INTEGER NOT NULL,
  first_ts_utc TEXT,
  last_ts_utc TEXT,
  PRIMARY KEY (entity_id, device, modality)
);
CREATE INDEX IF NOT EXISTS idx_wemp_entity ON wearable_entity_mentions_public(entity_id);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
