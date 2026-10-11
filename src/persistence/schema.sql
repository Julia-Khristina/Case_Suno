-- Initial migration placeholder. Full schema is implemented in Block 1.
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations (name)
VALUES ('000_block0_placeholder')
ON CONFLICT DO NOTHING;