-- Schema v2: resumable, fenced background runs.
-- Fresh local databases create these columns through SQLAlchemy metadata;
-- this migration records the equivalent change for an existing v1 database.
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS checkpoint JSON NOT NULL DEFAULT '{}';
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS checkpoint_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS checkpoint_sample_digest VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS checkpoint_config_digest VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS owner_token VARCHAR(128) NOT NULL DEFAULT '';
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS claim_generation INTEGER NOT NULL DEFAULT 0;
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMP NULL;
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT now();
SELECT 'venue-frontier schema v2';
