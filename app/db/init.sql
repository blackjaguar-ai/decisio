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
    decided_by      TEXT,
    offer_id        TEXT,
    rules_version   TEXT,
    selected_amount NUMERIC(12, 2),
    notice_type     TEXT,
    idempotency_key TEXT,
    response_json   JSONB,
    explanation     JSONB
);

-- Migración idempotente para instalaciones existentes (el VPS ya tenía esta tabla
-- creada antes de que estas columnas existieran).
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS offer_id        TEXT;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS rules_version   TEXT;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS selected_amount NUMERIC(12, 2);
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS notice_type     TEXT;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS response_json   JSONB;
-- Semana 2: la explicación completa (ai_explanation) se guarda en su propia
-- columna. Antes, GET /decision/{id} (polling de la vista cliente mientras
-- espera resolución humana) solo podía leer el resumen condensado que quedó
-- en `traces.payload` para el paso `ai_explainer` (step/outcome/summary/mode)
-- -- perdía explanation_for_customer, factors_considered, next_steps y
-- compliance_note. Se detectó probando el ciclo completo en sandbox contra
-- Postgres real, no en el papel.
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS explanation     JSONB;

-- Fix #8: una idempotency_key no puede mapear a dos decisiones distintas.
-- Índice parcial (solo sobre valores no nulos) porque la mayoría de requests
-- de demo no la mandan.
CREATE UNIQUE INDEX IF NOT EXISTS idx_decisions_idempotency_key
    ON decisions(idempotency_key) WHERE idempotency_key IS NOT NULL;

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
    resolved_by       TEXT,
    context           JSONB
);

-- Semana 2: `context` guarda {customer, offer, selected_amount} -- el mismo
-- payload que se le pasa a interrupt() en human_in_loop.py. Sin esto, la
-- bandeja del agente solo tenía motivo de escalamiento + recomendación AI,
-- pero no el perfil del cliente ni el rango de la oferta -- exactamente lo
-- que el Spec (§7) exige que el agente vea antes de resolver.
ALTER TABLE cases ADD COLUMN IF NOT EXISTS context JSONB;

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
