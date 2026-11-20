-- PREVIEW/STAGING ONLY: initialize an EMPTY, SEPARATE D1 database.
-- DO NOT run against fusebura-stamp-rally-db (production).
-- This schema is a minimal compatibility fixture derived from the existing API,
-- not a snapshot of the live production schema.
CREATE TABLE IF NOT EXISTS participants (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spots (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS stamps (
  id INTEGER PRIMARY KEY,
  participant_id TEXT NOT NULL,
  spot_id TEXT NOT NULL,
  acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  scan_order INTEGER NOT NULL
);

INSERT OR IGNORE INTO spots (id, type, name, active) VALUES
  ('v1', 'venue', '会場1', 1),
  ('v2', 'venue', '会場2', 1),
  ('v3', 'venue', '会場3', 1),
  ('v4', 'venue', '会場4', 1),
  ('v5', 'venue', '会場5', 1),
  ('s01', 'store', '参加店舗01', 1),
  ('s02', 'store', '参加店舗02', 1),
  ('s03', 'store', '参加店舗03', 1),
  ('s04', 'store', '参加店舗04', 1),
  ('s05', 'store', '参加店舗05', 1),
  ('s06', 'store', '参加店舗06', 1),
  ('s07', 'store', '参加店舗07', 1),
  ('s08', 'store', '参加店舗08', 1),
  ('s09', 'store', '参加店舗09', 1),
  ('s10', 'store', '参加店舗10', 1),
  ('s11', 'store', '参加店舗11', 1),
  ('s12', 'store', '参加店舗12', 1),
  ('s13', 'store', '参加店舗13', 1),
  ('s14', 'store', '参加店舗14', 1),
  ('s15', 'store', '参加店舗15', 1),
  ('s16', 'store', '参加店舗16', 1),
  ('s17', 'store', '参加店舗17', 1),
  ('s18', 'store', '参加店舗18', 1),
  ('s19', 'store', '参加店舗19', 1),
  ('s20', 'store', '参加店舗20', 1);

-- The unique index is intentionally a separate migration:
-- migrations/0001_unique_scan_order.sql
-- Once this PREVIEW schema exists, apply that migration to PREVIEW only.
