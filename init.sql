-- DECISIO — Schema de negocio
-- psycopg v3 — driver único en todo el proyecto

CREATE TABLE IF NOT EXISTS decisions (
    id              TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    route           TEXT NOT NULL,
    final_outcome   TEXT NOT NULL,
    approved_amount NUMERIC(12, 2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    decided_by      TEXT
);

CREATE TABLE IF NOT EXISTS traces (
    id          BIGSERIAL PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    step        TEXT NOT NULL,
    payload     JSONB NOT NULL,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cases (
    id                TEXT PRIMARY KEY,
    decision_id       TEXT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    status            TEXT NOT NULL DEFAULT 'pending',
    ai_summary        TEXT,
    ai_recommendation TEXT,
    ai_confidence     NUMERIC(4, 3),
    escalation_reason TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at       TIMESTAMPTZ,
    resolution        TEXT,
    resolution_amount NUMERIC(12, 2),
    resolved_by       TEXT
);

CREATE TABLE IF NOT EXISTS metrics (
    id          BIGSERIAL PRIMARY KEY,
    decision_id TEXT NOT NULL,
    path        TEXT NOT NULL,
    latency_ms  INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_created_at ON decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_decision_id   ON traces(decision_id);
CREATE INDEX IF NOT EXISTS idx_cases_status         ON cases(status);
CREATE INDEX IF NOT EXISTS idx_metrics_path         ON metrics(path);
CREATE INDEX IF NOT EXISTS idx_metrics_created_at   ON metrics(created_at DESC);
