-- Step 2.4 of the MoJ connector prompt: external-source provenance
-- columns so the connector can detect changes between sync runs.
--
-- source_external_id  : the connector's stable ID for the item
--                       (MoJ: the statute "serial" slug)
-- source_external_etag: connector-specific change-detection token
--                       (MoJ: statuteVersionId)
-- source_updated_at   : when the source last published the item
--                       (MoJ: publishDateGerogian)
--
-- The unique index lets sync() do upserts keyed on
-- (source_connector_id, source_external_id).

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS source_external_id TEXT,
  ADD COLUMN IF NOT EXISTS source_external_etag TEXT,
  ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS documents_source_external_uniq
  ON documents (source_connector_id, source_external_id)
  WHERE source_external_id IS NOT NULL;
