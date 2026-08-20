-- ============================================================================
-- AI Public Opinion Platform — schema
-- Postgres 16 + pgvector
-- Jalankan: psql $DATABASE_URL -f db/schema.sql lalu -f db/rls.sql
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "citext";

-- ---------------------------------------------------------------- enums ----

CREATE TYPE signal_source   AS ENUM ('SURVEY', 'SOCIAL', 'MEDIA', 'DIGITAL');
CREATE TYPE sampling_method AS ENUM ('SRS', 'STRATIFIED', 'CLUSTER', 'MULTISTAGE', 'QUOTA', 'PURPOSIVE');
CREATE TYPE user_role       AS ENUM ('SUPER_ADMIN', 'RESEARCH_DIRECTOR', 'RESEARCHER', 'DATA_ANALYST',
                                     'COMM_STRATEGIST', 'EXECUTIVE', 'CLIENT', 'VIEWER');
CREATE TYPE question_type   AS ENUM ('SINGLE', 'MULTI', 'LIKERT', 'SEMANTIC_DIFF', 'RANKING',
                                     'MATRIX', 'OPEN', 'DEMOGRAPHIC', 'SCREENING');
CREATE TYPE review_status   AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'NEEDS_REVIEW');
CREATE TYPE confidence_band AS ENUM ('LOW', 'MEDIUM', 'HIGH');
CREATE TYPE quality_flag    AS ENUM ('SPEEDING', 'STRAIGHT_LINING', 'INCONSISTENT',
                                     'DUPLICATE_SUSPECT', 'OUT_OF_QUOTA');

-- ------------------------------------------------------------- tenancy ----

CREATE TABLE organizations (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text NOT NULL,
    slug         text NOT NULL UNIQUE,
    plan         text NOT NULL DEFAULT 'starter',
    -- retensi data mentah dalam hari; dipakai job penghapusan terjadwal
    retention_days integer NOT NULL DEFAULT 730,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email         citext,
    full_name     text NOT NULL,
    password_hash text,
    role          user_role NOT NULL DEFAULT 'VIEWER',
    mfa_secret    text,
    is_active     boolean NOT NULL DEFAULT true,
    last_login_at timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, email)
);

CREATE TABLE projects (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        text NOT NULL,
    objective   text,
    -- bobot dimensi POI, per proyek. Lihat services/poi.py
    poi_weights jsonb NOT NULL DEFAULT
        '{"sentiment":20,"approval":25,"trust":25,"satisfaction":12,"issue_perception":10,"confidence":8}',
    is_demo     boolean NOT NULL DEFAULT false,
    created_by  uuid REFERENCES users(id),
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON projects (org_id);

-- -------------------------------------------------------------- survey ----

CREATE TABLE surveys (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    wave            integer NOT NULL DEFAULT 1,
    title           text NOT NULL,
    sampling_method sampling_method NOT NULL DEFAULT 'MULTISTAGE',
    target_n        integer,
    fielded_from    date,
    fielded_to      date,
    -- asumsi statistik yang dipakai saat menghitung target_n, disimpan agar
    -- laporan bisa menampilkan metodologi apa adanya
    sampling_params jsonb NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, wave)
);
CREATE INDEX ON surveys (org_id, project_id);

CREATE TABLE questions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    survey_id   uuid NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    position    integer NOT NULL,
    code        text NOT NULL,
    type        question_type NOT NULL,
    text        text NOT NULL,
    options     jsonb NOT NULL DEFAULT '[]',
    required    boolean NOT NULL DEFAULT true,
    -- dimensi POI yang disuplai item ini, mis. 'trust'. NULL = tidak masuk indeks
    poi_dimension text,
    reverse_scored boolean NOT NULL DEFAULT false,
    UNIQUE (survey_id, code)
);
CREATE INDEX ON questions (org_id, survey_id);

-- Responden dipisah dari identitasnya. Analisis hanya menyentuh tabel ini.
CREATE TABLE respondents (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    survey_id      uuid NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    anon_code      text NOT NULL,
    age_band       text,
    gender         text,
    education      text,
    occupation     text,
    province_code  text,
    urbanicity     text,
    -- bobot pasca-stratifikasi; 1.0 kalau belum dibobot
    weight         numeric(8,4) NOT NULL DEFAULT 1.0,
    completed_at   timestamptz,
    duration_sec   integer,
    quality_score  integer,
    quality_flags  quality_flag[] NOT NULL DEFAULT '{}',
    UNIQUE (survey_id, anon_code)
);
CREATE INDEX ON respondents (org_id, survey_id);
CREATE INDEX ON respondents (province_code);

-- PII terpisah, retensi sendiri, akses dibatasi peran. Boleh kosong.
CREATE TABLE respondent_identities (
    respondent_id uuid PRIMARY KEY REFERENCES respondents(id) ON DELETE CASCADE,
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    contact_hash  text NOT NULL,
    consent_at    timestamptz NOT NULL,
    consent_scope text NOT NULL,
    purge_after   date NOT NULL
);

CREATE TABLE responses (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    respondent_id uuid NOT NULL REFERENCES respondents(id) ON DELETE CASCADE,
    question_id   uuid NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    value_num     numeric(10,4),
    value_text    text,
    value_json    jsonb,
    answered_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (respondent_id, question_id)
);
CREATE INDEX ON responses (org_id, question_id);

-- ------------------------------------------------- signals: social/media ----

CREATE TABLE data_sources (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source      signal_source NOT NULL,
    connector   text NOT NULL,              -- 'youtube_api', 'x_api', 'gdelt', ...
    config      jsonb NOT NULL DEFAULT '{}',
    is_active   boolean NOT NULL DEFAULT true,
    last_sync_at timestamptz
);
CREATE INDEX ON data_sources (org_id, project_id);

CREATE TABLE mentions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source        signal_source NOT NULL,
    connector     text NOT NULL,
    external_id   text NOT NULL,
    published_at  timestamptz NOT NULL,
    author_hash   text,                     -- akun di-hash, bukan disimpan mentah
    text          text NOT NULL,
    lang          text DEFAULT 'id',
    engagement    integer NOT NULL DEFAULT 0,
    reach_est     integer,
    province_code text,
    sentiment     numeric(4,3),             -- -1..1
    emotion       jsonb,                    -- {anger:0.2, fear:0.1, ...}
    topic_id      uuid,
    narrative_id  uuid,
    embedding     vector(1024),
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, connector, external_id)
);
CREATE INDEX ON mentions (org_id, project_id, published_at DESC);
CREATE INDEX ON mentions (project_id, source, published_at DESC);
CREATE INDEX ON mentions USING hnsw (embedding vector_cosine_ops);

CREATE TABLE topics (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id  uuid REFERENCES topics(id) ON DELETE SET NULL,
    label      text NOT NULL,
    keywords   text[] NOT NULL DEFAULT '{}',
    centroid   vector(1024),
    volume     integer NOT NULL DEFAULT 0
);

CREATE TABLE narratives (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code          text NOT NULL,            -- 'A', 'B', ...
    statement     text NOT NULL,
    origin_source signal_source NOT NULL,
    volume_pct    numeric(5,2) NOT NULL,
    momentum_7d   numeric(5,2) NOT NULL DEFAULT 0,
    sentiment     numeric(4,3),
    media_pickup  integer NOT NULL DEFAULT 0,
    -- klaster mana yang tidak terklasifikasi; ditampilkan sebagai batasan
    unclustered_pct numeric(5,2) NOT NULL DEFAULT 0,
    detected_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, code)
);

-- --------------------------------------------------------- measurements ----

-- Snapshot metrik per periode. Semua metrik WAJIB punya source + method.
CREATE TABLE metric_snapshots (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    metric        text NOT NULL,            -- 'poi', 'trust', 'approval', 'risk', ...
    source        signal_source NOT NULL,
    method        text NOT NULL,
    period_start  date NOT NULL,
    period_end    date NOT NULL,
    value         numeric(8,3) NOT NULL,
    ci_low        numeric(8,3),
    ci_high       numeric(8,3),
    effective_n   integer,
    province_code text,                      -- NULL = nasional
    segment       text,                      -- NULL = seluruh sampel
    breakdown     jsonb NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON metric_snapshots (org_id, project_id, metric, period_end DESC);
CREATE INDEX ON metric_snapshots (project_id, province_code, metric);

CREATE TABLE segments (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        text NOT NULL,
    size_pct    numeric(5,2) NOT NULL,
    sentiment   numeric(5,2),
    trust       numeric(5,2),
    profile     jsonb NOT NULL DEFAULT '{}',
    method      text NOT NULL DEFAULT 'latent_class',
    entropy     numeric(4,3),
    UNIQUE (project_id, name)
);

CREATE TABLE timeline_events (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    occurred_at timestamptz NOT NULL,
    kind        text NOT NULL,              -- 'event' | 'signal' | 'media' | 'alert'
    label       text NOT NULL,
    value_note  text,
    -- keterkaitan, bukan sebab. Lihat CLAUDE.md §3
    associated_metric text
);
CREATE INDEX ON timeline_events (org_id, project_id, occurred_at DESC);

CREATE TABLE forecasts (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id   uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    metric       text NOT NULL,
    horizon_days integer NOT NULL,
    expected     numeric(8,3) NOT NULL,
    pi_low       numeric(8,3) NOT NULL,
    pi_high      numeric(8,3) NOT NULL,
    pi_level     numeric(4,3) NOT NULL DEFAULT 0.80,
    model        text NOT NULL,
    drivers      jsonb NOT NULL DEFAULT '[]',
    is_simulation boolean NOT NULL DEFAULT false,
    scenario     jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON forecasts (org_id, project_id, metric, created_at DESC);

-- ---------------------------------------------------------- governance ----

-- Satu baris per keluaran AI. Tanpa baris di sini, keluaran tidak boleh
-- ditampilkan di UI. Lihat app/ai/envelope.py
CREATE TABLE ai_outputs (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind          text NOT NULL,            -- 'executive_brief', 'narrative_label', ...
    model_version text NOT NULL,
    method        text NOT NULL,
    prompt_hash   text NOT NULL,
    payload       jsonb NOT NULL,
    evidence      jsonb NOT NULL,           -- referensi ke metric_snapshots / mentions
    confidence    confidence_band NOT NULL,
    limitations   text NOT NULL,
    human_review  review_status NOT NULL DEFAULT 'PENDING',
    reviewed_by   uuid REFERENCES users(id),
    reviewed_at   timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_outputs_evidence_not_empty CHECK (jsonb_array_length(evidence) > 0),
    CONSTRAINT ai_outputs_limitations_not_blank CHECK (length(btrim(limitations)) > 0)
);
CREATE INDEX ON ai_outputs (org_id, project_id, created_at DESC);

CREATE TABLE audit_logs (
    id          bigserial PRIMARY KEY,
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_id    uuid REFERENCES users(id),
    action      text NOT NULL,
    entity      text NOT NULL,
    entity_id   uuid,
    ip          inet,
    metadata    jsonb NOT NULL DEFAULT '{}',
    at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON audit_logs (org_id, at DESC);

CREATE TABLE data_quality_scores (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset     text NOT NULL,
    completeness  integer NOT NULL,
    duplicate     integer NOT NULL,
    response_qual integer NOT NULL,
    consistency   integer NOT NULL,
    sample_balance integer NOT NULL,
    metadata_score integer NOT NULL,
    overall       integer NOT NULL,
    computed_at   timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------- helpers ----

CREATE OR REPLACE VIEW v_latest_poi AS
SELECT DISTINCT ON (project_id)
       project_id, value, ci_low, ci_high, effective_n, period_end, method
FROM   metric_snapshots
WHERE  metric = 'poi' AND province_code IS NULL AND segment IS NULL
ORDER  BY project_id, period_end DESC;
