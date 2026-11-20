-- Stamp order is unique per participant. Re-visits to a spot are allowed
-- when separated by a different spot (A -> B -> A).
-- Apply to a SEPARATE TEST D1 database first; do NOT apply to production automatically.
-- Preflight first: SELECT participant_id, scan_order, COUNT(*) AS n
-- FROM stamps GROUP BY participant_id, scan_order HAVING COUNT(*) > 1;
CREATE UNIQUE INDEX IF NOT EXISTS idx_stamps_participant_scan_order
  ON stamps (participant_id, scan_order);
