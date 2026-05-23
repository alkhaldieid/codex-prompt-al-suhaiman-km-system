CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
  CREATE TYPE user_role AS ENUM ('lawyer', 'reviewer', 'km_lead', 'admin');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE document_status AS ENUM (
    'uploaded', 'processing', 'pending_review', 'published',
    'archived', 'rejected', 'duplicate_of'
  );
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE source_track AS ENUM (
    'track1_external', 'track2_legacy', 'track3_capture', 'synthetic'
  );
EXCEPTION WHEN duplicate_object THEN null; END $$;

CREATE TABLE IF NOT EXISTS documents (
  doc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title_ar TEXT NOT NULL,
  title_en TEXT,
  doc_type TEXT NOT NULL,
  practice_area TEXT[] NOT NULL DEFAULT '{}',
  jurisdiction TEXT NOT NULL DEFAULT 'KSA',
  issuing_body_ar TEXT,
  issuing_body_en TEXT,
  date_gregorian DATE,
  date_hijri TEXT,
  case_number TEXT,
  language JSONB NOT NULL DEFAULT '{"primary":"ar","ar_ratio":1,"en_ratio":0}',
  keywords_ar TEXT[] NOT NULL DEFAULT '{}',
  source_track source_track NOT NULL,
  source_url TEXT,
  source_connector_id TEXT,
  visibility TEXT NOT NULL DEFAULT 'firm_wide',
  privilege_flag BOOLEAN NOT NULL DEFAULT false,
  pii_flags TEXT[] NOT NULL DEFAULT '{}',
  status document_status NOT NULL DEFAULT 'uploaded',
  duplicate_of_doc_id UUID REFERENCES documents(doc_id),
  content_hash_sha256 TEXT,
  ocr_metadata JSONB,
  summary_ar TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version INTEGER NOT NULL DEFAULT 1,
  audit_log_ref TEXT
);

CREATE TABLE IF NOT EXISTS document_chunks (
  chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  text_ar TEXT NOT NULL,
  text_normalized TEXT NOT NULL,
  embedding vector(1024),
  page_no INTEGER,
  paragraph_no INTEGER,
  char_start INTEGER,
  char_end INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(doc_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS document_parties (
  party_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  name_ar TEXT NOT NULL,
  name_en TEXT,
  role TEXT NOT NULL DEFAULT 'other'
);

CREATE TABLE IF NOT EXISTS audit_log (
  event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  actor_user_id UUID,
  actor_role TEXT,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  details JSONB NOT NULL DEFAULT '{}',
  ip TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS external_llm_calls (
  event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  action TEXT NOT NULL DEFAULT 'external_llm_call',
  model TEXT NOT NULL,
  purpose TEXT NOT NULL,
  doc_id UUID,
  doc_source_track source_track,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS connector_runs (
  run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  connector_id TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  items_fetched INTEGER NOT NULL DEFAULT 0,
  items_new INTEGER NOT NULL DEFAULT 0,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS feedback_signals (
  signal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID,
  doc_id UUID,
  signal_type TEXT NOT NULL,
  details JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
