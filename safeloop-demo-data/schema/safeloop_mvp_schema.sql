-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-10-11T15:46:24.673Z

CREATE TYPE "user_role" AS ENUM (
  'process_safety_engineer',
  'reliability_engineer',
  'operator',
  'trainee',
  'plant_manager',
  'auditor',
  'admin'
);

CREATE TYPE "data_origin" AS ENUM (
  'synthetic',
  'public_proxy',
  'real'
);

CREATE TYPE "health_band" AS ENUM (
  'healthy',
  'degraded',
  'critical'
);

CREATE TYPE "guide_word" AS ENUM (
  'no',
  'less',
  'more',
  'reverse',
  'as_well_as',
  'part_of',
  'other_than',
  'high',
  'low'
);

CREATE TYPE "hazop_param" AS ENUM (
  'flow',
  'pressure',
  'temperature',
  'level',
  'composition',
  'other'
);

CREATE TYPE "safeguard_type" AS ENUM (
  'bpcs',
  'alarm',
  'ipl',
  'procedure',
  'sis',
  'mechanical'
);

CREATE TYPE "record_status" AS ENUM (
  'draft',
  'under_review',
  'approved',
  'superseded',
  'rejected'
);

CREATE TYPE "doc_type" AS ENUM (
  'manual',
  'sop',
  'alarm_response',
  'incident',
  'maintenance_report',
  'hazop',
  'asset_model',
  'shift_log',
  'rca_report'
);

CREATE TYPE "agent_name" AS ENUM (
  'health_agent',
  'risk_engine',
  'red_team',
  'judge',
  'knowledge_agent',
  'guardrail',
  'reporter'
);

CREATE TYPE "verdict" AS ENUM (
  'pass',
  'block',
  'revise'
);

CREATE TYPE "artifact_type" AS ENUM (
  'hazop_change',
  'risk_rescore',
  'maintenance_recommendation',
  'moc_draft',
  'rca_report'
);

CREATE TYPE "approval_decision" AS ENUM (
  'pending',
  'approved',
  'rejected'
);

CREATE TYPE "citation_target" AS ENUM (
  'chunk',
  'asset',
  'tag_window',
  'hazop_row'
);

CREATE TABLE "sites" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "code" varchar(32) UNIQUE NOT NULL,
  "name" varchar(200) NOT NULL,
  "origin" data_origin NOT NULL DEFAULT 'synthetic',
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "units" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "site_id" uuid NOT NULL,
  "code" varchar(32) NOT NULL,
  "name" varchar(200) NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "process_nodes" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "unit_id" uuid NOT NULL,
  "code" varchar(16) NOT NULL,
  "name" varchar(200) NOT NULL,
  "design_intent" text NOT NULL
);

CREATE TABLE "assets" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "unit_id" uuid NOT NULL,
  "node_id" uuid,
  "tag" varchar(32) NOT NULL,
  "name" varchar(200) NOT NULL,
  "asset_class" varchar(64) NOT NULL,
  "criticality" char(1),
  "standby_of_id" uuid,
  "is_monitored" boolean NOT NULL DEFAULT false,
  "origin" data_origin NOT NULL DEFAULT 'synthetic'
);

CREATE TABLE "asset_links" (
  "code" varchar(16) UNIQUE NOT NULL,
  "from_asset_id" uuid NOT NULL,
  "to_asset_id" uuid NOT NULL,
  "relation" varchar(32) NOT NULL,
  PRIMARY KEY ("from_asset_id", "to_asset_id", "relation")
);

CREATE TABLE "sensor_tags" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "asset_id" uuid NOT NULL,
  "tag" varchar(64) UNIQUE NOT NULL,
  "description" varchar(200),
  "eng_unit" varchar(16) NOT NULL,
  "alert_low" numeric,
  "alert_high" numeric,
  "alert_high_tightened" numeric,
  "source_dataset" varchar(64),
  "source_signal" varchar(128),
  "transform" text,
  "origin" data_origin NOT NULL DEFAULT 'public_proxy'
);

CREATE TABLE "replay_runs" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "scenario_code" varchar(8) NOT NULL,
  "speed" smallint NOT NULL DEFAULT 3,
  "started_by" uuid,
  "started_at" timestamptz NOT NULL DEFAULT (now()),
  "ended_at" timestamptz,
  "final_hour" smallint
);

CREATE TABLE "sensor_readings" (
  "replay_run_id" uuid NOT NULL,
  "tag_id" uuid NOT NULL,
  "replay_hour" smallint NOT NULL,
  "ts" timestamptz NOT NULL DEFAULT (now()),
  "value" numeric NOT NULL,
  "quality" varchar(12) NOT NULL DEFAULT 'good',
  PRIMARY KEY ("replay_run_id", "tag_id", "replay_hour")
);

CREATE TABLE "health_assessments" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "replay_run_id" uuid NOT NULL,
  "asset_id" uuid NOT NULL,
  "replay_hour" smallint NOT NULL,
  "health_index" smallint NOT NULL,
  "band" health_band NOT NULL,
  "previous_band" health_band,
  "model_version" varchar(32) NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "hazop_rows" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "node_id" uuid NOT NULL,
  "row_code" varchar(24) NOT NULL,
  "version" int NOT NULL DEFAULT 1,
  "guide_word" guide_word NOT NULL,
  "parameter" hazop_param NOT NULL,
  "deviation" text NOT NULL,
  "cause" text NOT NULL,
  "cause_asset_id" uuid,
  "consequence" text NOT NULL,
  "severity" smallint NOT NULL,
  "likelihood_base" smallint NOT NULL,
  "status" record_status NOT NULL DEFAULT 'approved',
  "supersedes_id" uuid,
  "created_by_agent" agent_name,
  "created_by_user" uuid,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "hazop_recommendations" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "hazop_row_id" uuid NOT NULL,
  "text" text NOT NULL,
  "owner_role" user_role
);

CREATE TABLE "safeguards" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "unit_id" uuid NOT NULL,
  "ref_code" varchar(64) NOT NULL,
  "type" safeguard_type NOT NULL,
  "description" text,
  "last_test_date" date
);

CREATE TABLE "hazop_row_safeguards" (
  "hazop_row_id" uuid NOT NULL,
  "safeguard_id" uuid NOT NULL,
  "credited" boolean NOT NULL DEFAULT true,
  PRIMARY KEY ("hazop_row_id", "safeguard_id")
);

CREATE TABLE "safeguard_dependencies" (
  "safeguard_id" uuid NOT NULL,
  "asset_id" uuid NOT NULL,
  PRIMARY KEY ("safeguard_id", "asset_id")
);

CREATE TABLE "risk_rule_sets" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "version" varchar(16) UNIQUE NOT NULL,
  "rules" jsonb NOT NULL,
  "status" record_status NOT NULL DEFAULT 'draft',
  "approved_by" uuid,
  "approved_at" timestamptz,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "risk_rescores" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "hazop_row_id" uuid NOT NULL,
  "rule_set_id" uuid NOT NULL,
  "replay_run_id" uuid,
  "trigger_health_id" uuid,
  "likelihood_old" smallint NOT NULL,
  "likelihood_new" smallint NOT NULL,
  "severity" smallint NOT NULL,
  "score_old" smallint NOT NULL,
  "score_new" smallint NOT NULL,
  "rules_applied" text[] NOT NULL,
  "safeguards_lost" uuid[],
  "computed_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "documents" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "doc_code" varchar(32) NOT NULL,
  "title" varchar(300) NOT NULL,
  "type" doc_type NOT NULL,
  "revision" varchar(16) NOT NULL DEFAULT 'A',
  "effective_date" date,
  "is_current" boolean NOT NULL DEFAULT true,
  "origin" data_origin NOT NULL DEFAULT 'synthetic',
  "generator_model" varchar(64),
  "reviewed_by" uuid,
  "storage_uri" text,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "document_assets" (
  "document_id" uuid NOT NULL,
  "asset_id" uuid NOT NULL,
  PRIMARY KEY ("document_id", "asset_id")
);

CREATE TABLE "document_chunks" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "document_id" uuid NOT NULL,
  "chunk_index" int NOT NULL,
  "text" text NOT NULL,
  "page" int,
  "section" varchar(200),
  "token_count" int,
  "qdrant_point_id" uuid UNIQUE NOT NULL,
  "embedding_model" varchar(64) NOT NULL
);

CREATE TABLE "users" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "handle" varchar(32) UNIQUE NOT NULL,
  "display_name" varchar(120) NOT NULL,
  "email" varchar(200) UNIQUE,
  "role" user_role NOT NULL,
  "is_demo" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "prompt_templates" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "agent" agent_name NOT NULL,
  "version" varchar(16) NOT NULL,
  "template" text NOT NULL,
  "output_schema" jsonb,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "agent_runs" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "agent" agent_name NOT NULL,
  "prompt_template_id" uuid,
  "model_id" varchar(64),
  "model_endpoint" varchar(32),
  "input" jsonb NOT NULL,
  "output" jsonb,
  "schema_valid" boolean,
  "input_tokens" int,
  "output_tokens" int,
  "latency_ms" int,
  "error" text,
  "hazop_row_id" uuid,
  "chat_message_id" uuid,
  "started_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "hazop_proposals" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "agent_run_id" uuid NOT NULL,
  "target_row_id" uuid NOT NULL,
  "guide_word" guide_word NOT NULL,
  "parameter" hazop_param NOT NULL,
  "deviation" text NOT NULL,
  "cause" text NOT NULL,
  "consequence" text,
  "proposed_safeguards" text[],
  "recommendation" text,
  "resulting_row_id" uuid
);

CREATE TABLE "judge_verdicts" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "proposal_id" uuid,
  "chat_message_id" uuid,
  "verdict" verdict NOT NULL,
  "unknown_entities" text[],
  "unresolved_citations" text[],
  "actuation_wording" boolean NOT NULL DEFAULT false,
  "reason" text,
  "checked_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "approval_items" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "artifact_type" artifact_type NOT NULL,
  "title" varchar(300) NOT NULL,
  "asset_id" uuid,
  "proposal_id" uuid,
  "rescore_id" uuid,
  "body" jsonb,
  "confidence" varchar(8) NOT NULL,
  "judge_verdict_id" uuid,
  "decision" approval_decision NOT NULL DEFAULT 'pending',
  "decided_by" uuid,
  "decision_reason" text,
  "edited_body" jsonb,
  "created_at" timestamptz NOT NULL DEFAULT (now()),
  "decided_at" timestamptz
);

CREATE TABLE "chat_sessions" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "user_id" uuid NOT NULL,
  "started_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "chat_messages" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "session_id" uuid NOT NULL,
  "role" varchar(10) NOT NULL,
  "content" text NOT NULL,
  "kind" varchar(16),
  "confidence" varchar(8),
  "guardrail_reason" varchar(64),
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "citations" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "target_type" citation_target NOT NULL,
  "chunk_id" uuid,
  "asset_id" uuid,
  "tag_id" uuid,
  "hour_from" smallint,
  "hour_to" smallint,
  "hazop_row_id" uuid,
  "resolved" boolean NOT NULL DEFAULT true,
  "raw_ref" varchar(128),
  "chat_message_id" uuid,
  "proposal_id" uuid,
  "approval_item_id" uuid,
  "rescore_id" uuid
);

CREATE TABLE "audit_log" (
  "id" bigserial PRIMARY KEY,
  "occurred_at" timestamptz NOT NULL DEFAULT (now()),
  "action" varchar(48) NOT NULL,
  "actor_agent" agent_name,
  "actor_user" uuid,
  "entity_table" varchar(48) NOT NULL,
  "entity_id" uuid NOT NULL,
  "model_id" varchar(64),
  "prompt_version" varchar(16),
  "rule_set_version" varchar(16),
  "replay_run_id" uuid,
  "replay_hour" smallint,
  "detail" jsonb
);

CREATE TABLE "golden_items" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "item_code" varchar(16) UNIQUE NOT NULL,
  "set_name" varchar(32) NOT NULL,
  "split" varchar(8) NOT NULL DEFAULT 'test',
  "input" jsonb NOT NULL,
  "expected" jsonb NOT NULL,
  "authored_by" uuid,
  "reviewed_by" uuid,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "eval_runs" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "started_at" timestamptz NOT NULL DEFAULT (now()),
  "finished_at" timestamptz,
  "git_sha" varchar(40),
  "model_id" varchar(64),
  "rule_set_id" uuid,
  "dataset_hash" varchar(64),
  "is_frozen" boolean NOT NULL DEFAULT false
);

CREATE TABLE "eval_results" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "eval_run_id" uuid NOT NULL,
  "objective_code" varchar(8) NOT NULL,
  "metric" varchar(64) NOT NULL,
  "value" numeric,
  "target" numeric,
  "passed" boolean,
  "sample_size" int
);

CREATE TABLE "eval_item_results" (
  "eval_run_id" uuid NOT NULL,
  "golden_item_id" uuid NOT NULL,
  "passed" boolean NOT NULL,
  "output" jsonb,
  "agent_run_id" uuid,
  PRIMARY KEY ("eval_run_id", "golden_item_id")
);

CREATE UNIQUE INDEX ON "units" ("site_id", "code");

CREATE UNIQUE INDEX ON "process_nodes" ("unit_id", "code");

CREATE UNIQUE INDEX ON "assets" ("unit_id", "tag");

CREATE UNIQUE INDEX ON "health_assessments" ("replay_run_id", "asset_id", "replay_hour");

CREATE INDEX ON "health_assessments" ("asset_id", "created_at");

CREATE UNIQUE INDEX ON "hazop_rows" ("node_id", "row_code", "version");

CREATE INDEX ON "hazop_rows" ("status");

CREATE UNIQUE INDEX ON "safeguards" ("unit_id", "ref_code");

CREATE INDEX ON "risk_rescores" ("hazop_row_id", "computed_at");

CREATE UNIQUE INDEX ON "documents" ("doc_code", "revision");

CREATE UNIQUE INDEX ON "document_chunks" ("document_id", "chunk_index");

CREATE UNIQUE INDEX ON "prompt_templates" ("agent", "version");

CREATE INDEX ON "approval_items" ("decision");

CREATE INDEX ON "approval_items" ("artifact_type", "created_at");

CREATE INDEX ON "chat_messages" ("session_id", "created_at");

CREATE INDEX ON "audit_log" ("entity_table", "entity_id");

CREATE INDEX ON "audit_log" ("occurred_at");

CREATE UNIQUE INDEX ON "eval_results" ("eval_run_id", "objective_code", "metric");

COMMENT ON COLUMN "sites"."code" IS 'e.g. DEMO-SITE';

COMMENT ON COLUMN "units"."code" IS 'e.g. U100';

COMMENT ON COLUMN "process_nodes"."code" IS 'N1, N2, N3';

COMMENT ON COLUMN "assets"."tag" IS 'P-101, TV-301, PSV-201';

COMMENT ON COLUMN "assets"."asset_class" IS 'centrifugal_pump, control_valve, psv, heat_exchanger';

COMMENT ON COLUMN "assets"."criticality" IS 'A / B / C';

COMMENT ON COLUMN "assets"."standby_of_id" IS 'P-101B is standby of P-101';

COMMENT ON TABLE "asset_links" IS 'Edges of the asset graph, e.g. P-101 suction_from S-101; PSV-201 protects V-201.';

COMMENT ON COLUMN "asset_links"."code" IS 'L-104; cited as asset_model:L-104 by agents and the Judge';

COMMENT ON COLUMN "asset_links"."relation" IS 'suction_from, protects, controls, feeds, measures, standby_for';

COMMENT ON COLUMN "sensor_tags"."tag" IS 'P101_DE_VIB_RMS';

COMMENT ON COLUMN "sensor_tags"."eng_unit" IS 'mm/s, °C, barg';

COMMENT ON COLUMN "sensor_tags"."alert_high_tightened" IS 'Set by rule R-P-01 for safety-critical assets';

COMMENT ON COLUMN "sensor_tags"."source_dataset" IS 'NASA IMS, TEP, synthetic';

COMMENT ON COLUMN "sensor_tags"."source_signal" IS 'Column or channel in the source dataset';

COMMENT ON COLUMN "sensor_tags"."transform" IS 'Feature extraction / rescaling applied';

COMMENT ON COLUMN "replay_runs"."scenario_code" IS 'S1, S2';

COMMENT ON COLUMN "replay_runs"."speed" IS '1x, 3x, 8x';

COMMENT ON TABLE "sensor_readings" IS 'Append-only. Consider TimescaleDB hypertable or monthly partitions after the MVP.';

COMMENT ON COLUMN "sensor_readings"."quality" IS 'good / bad / uncertain';

COMMENT ON COLUMN "health_assessments"."health_index" IS '0–100, rounded';

COMMENT ON COLUMN "health_assessments"."previous_band" IS 'Set when this row is a band change';

COMMENT ON COLUMN "health_assessments"."model_version" IS 'e.g. pca-hi-v1';

COMMENT ON TABLE "hazop_rows" IS 'Approved rows are immutable; a change creates a new version that supersedes the old one.';

COMMENT ON COLUMN "hazop_rows"."row_code" IS 'HZ-N1-003';

COMMENT ON COLUMN "hazop_rows"."cause_asset_id" IS 'Asset whose health drives likelihood';

COMMENT ON COLUMN "hazop_rows"."severity" IS '1–5';

COMMENT ON COLUMN "hazop_rows"."likelihood_base" IS '1–5, design basis';

COMMENT ON COLUMN "hazop_rows"."created_by_agent" IS 'Null when written by a person';

COMMENT ON COLUMN "safeguards"."ref_code" IS 'PSV-201, FAL-201, P-101B auto-start';

COMMENT ON TABLE "safeguard_dependencies" IS 'P-101B auto-start depends on P-101B and FT-201; TIC-301 loop depends on TV-301. Drives rule R-S-02.';

COMMENT ON COLUMN "risk_rule_sets"."version" IS 'v1.0';

COMMENT ON COLUMN "risk_rule_sets"."rules" IS '{"R-L-01":{"band":"degraded","dL":1}, "R-S-02":{...}}';

COMMENT ON COLUMN "risk_rule_sets"."approved_by" IS 'Process safety engineer';

COMMENT ON TABLE "risk_rescores" IS 'Deterministic output of the Risk Engine. No LLM involved. Append-only.';

COMMENT ON COLUMN "risk_rescores"."trigger_health_id" IS 'Band change that caused this re-score';

COMMENT ON COLUMN "risk_rescores"."rules_applied" IS '{''R-L-01'',''R-S-02''}';

COMMENT ON COLUMN "risk_rescores"."safeguards_lost" IS 'Safeguard ids whose credit was removed';

COMMENT ON COLUMN "documents"."doc_code" IS 'MAN-P101, SOP-P101-02, INC-2024-017; unique per revision';

COMMENT ON COLUMN "documents"."is_current" IS 'Superseded revisions excluded from retrieval';

COMMENT ON COLUMN "documents"."generator_model" IS 'Set for LLM-generated synthetic documents';

COMMENT ON COLUMN "documents"."storage_uri" IS 'Object-store path of the source file';

COMMENT ON COLUMN "users"."handle" IS 'Demo login handle: rina, dimas, agus, auditor, admin';

COMMENT ON COLUMN "prompt_templates"."version" IS 'redteam.v1';

COMMENT ON COLUMN "prompt_templates"."output_schema" IS 'JSON schema the output must validate against';

COMMENT ON COLUMN "agent_runs"."model_id" IS 'Null for rule-based components';

COMMENT ON COLUMN "agent_runs"."model_endpoint" IS 'cloud_api / vllm';

COMMENT ON COLUMN "agent_runs"."hazop_row_id" IS 'Row the Red Team was run on';

COMMENT ON COLUMN "hazop_proposals"."proposed_safeguards" IS 'As returned by the model, before grounding';

COMMENT ON COLUMN "hazop_proposals"."resulting_row_id" IS 'New row version created on approval';

COMMENT ON TABLE "judge_verdicts" IS 'Rule-based checks in code. Exactly one of proposal_id / chat_message_id is set (CHECK constraint).';

COMMENT ON COLUMN "approval_items"."body" IS 'Draft content for reports and recommendations';

COMMENT ON COLUMN "approval_items"."confidence" IS 'high / medium / low';

COMMENT ON COLUMN "approval_items"."decision_reason" IS 'Required when decision = rejected (CHECK)';

COMMENT ON COLUMN "approval_items"."edited_body" IS 'Reviewer edits, kept as a diff source';

COMMENT ON COLUMN "chat_messages"."role" IS 'user / assistant';

COMMENT ON COLUMN "chat_messages"."kind" IS 'answer / insufficient / refused';

COMMENT ON COLUMN "chat_messages"."guardrail_reason" IS 'Set when refused before any model call';

COMMENT ON TABLE "citations" IS 'Polymorphic evidence link. One owner (message / proposal / approval / rescore) and one target per row.';

COMMENT ON COLUMN "citations"."resolved" IS 'False = cited id did not resolve';

COMMENT ON COLUMN "citations"."raw_ref" IS 'Reference exactly as returned by the model';

COMMENT ON TABLE "audit_log" IS 'Append-only. Revoke UPDATE/DELETE from the app role; insert via trigger or service only.';

COMMENT ON COLUMN "audit_log"."action" IS 'health_band_changed, risk_rescore, draft_created, judge_block, approved, rejected, guardrail_refusal';

COMMENT ON COLUMN "golden_items"."item_code" IS 'GH-01, QA-01, OOC-01, GR-01, RCA-01';

COMMENT ON COLUMN "golden_items"."set_name" IS 'hazop_rows, qa, out_of_corpus, guardrail, rca';

COMMENT ON COLUMN "golden_items"."split" IS 'train / test; test never used in prompts';

COMMENT ON COLUMN "eval_runs"."is_frozen" IS 'True for the demo-day run';

COMMENT ON COLUMN "eval_results"."objective_code" IS 'PO-1 … PO-5';

ALTER TABLE "units" ADD FOREIGN KEY ("site_id") REFERENCES "sites" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "process_nodes" ADD FOREIGN KEY ("unit_id") REFERENCES "units" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "assets" ADD FOREIGN KEY ("unit_id") REFERENCES "units" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "assets" ADD FOREIGN KEY ("node_id") REFERENCES "process_nodes" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "assets" ADD FOREIGN KEY ("standby_of_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "asset_links" ADD FOREIGN KEY ("from_asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "asset_links" ADD FOREIGN KEY ("to_asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sensor_tags" ADD FOREIGN KEY ("asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "replay_runs" ADD FOREIGN KEY ("started_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sensor_readings" ADD FOREIGN KEY ("replay_run_id") REFERENCES "replay_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sensor_readings" ADD FOREIGN KEY ("tag_id") REFERENCES "sensor_tags" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "health_assessments" ADD FOREIGN KEY ("replay_run_id") REFERENCES "replay_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "health_assessments" ADD FOREIGN KEY ("asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_rows" ADD FOREIGN KEY ("node_id") REFERENCES "process_nodes" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_rows" ADD FOREIGN KEY ("cause_asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_rows" ADD FOREIGN KEY ("supersedes_id") REFERENCES "hazop_rows" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_rows" ADD FOREIGN KEY ("created_by_user") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_recommendations" ADD FOREIGN KEY ("hazop_row_id") REFERENCES "hazop_rows" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safeguards" ADD FOREIGN KEY ("unit_id") REFERENCES "units" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_row_safeguards" ADD FOREIGN KEY ("hazop_row_id") REFERENCES "hazop_rows" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_row_safeguards" ADD FOREIGN KEY ("safeguard_id") REFERENCES "safeguards" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safeguard_dependencies" ADD FOREIGN KEY ("safeguard_id") REFERENCES "safeguards" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safeguard_dependencies" ADD FOREIGN KEY ("asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "risk_rule_sets" ADD FOREIGN KEY ("approved_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "risk_rescores" ADD FOREIGN KEY ("hazop_row_id") REFERENCES "hazop_rows" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "risk_rescores" ADD FOREIGN KEY ("rule_set_id") REFERENCES "risk_rule_sets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "risk_rescores" ADD FOREIGN KEY ("replay_run_id") REFERENCES "replay_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "risk_rescores" ADD FOREIGN KEY ("trigger_health_id") REFERENCES "health_assessments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documents" ADD FOREIGN KEY ("reviewed_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document_assets" ADD FOREIGN KEY ("document_id") REFERENCES "documents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document_assets" ADD FOREIGN KEY ("asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document_chunks" ADD FOREIGN KEY ("document_id") REFERENCES "documents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "agent_runs" ADD FOREIGN KEY ("prompt_template_id") REFERENCES "prompt_templates" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "agent_runs" ADD FOREIGN KEY ("hazop_row_id") REFERENCES "hazop_rows" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "agent_runs" ADD FOREIGN KEY ("chat_message_id") REFERENCES "chat_messages" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_proposals" ADD FOREIGN KEY ("agent_run_id") REFERENCES "agent_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_proposals" ADD FOREIGN KEY ("target_row_id") REFERENCES "hazop_rows" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hazop_proposals" ADD FOREIGN KEY ("resulting_row_id") REFERENCES "hazop_rows" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "judge_verdicts" ADD FOREIGN KEY ("proposal_id") REFERENCES "hazop_proposals" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "judge_verdicts" ADD FOREIGN KEY ("chat_message_id") REFERENCES "chat_messages" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approval_items" ADD FOREIGN KEY ("asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approval_items" ADD FOREIGN KEY ("proposal_id") REFERENCES "hazop_proposals" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approval_items" ADD FOREIGN KEY ("rescore_id") REFERENCES "risk_rescores" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approval_items" ADD FOREIGN KEY ("judge_verdict_id") REFERENCES "judge_verdicts" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approval_items" ADD FOREIGN KEY ("decided_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "chat_sessions" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "chat_messages" ADD FOREIGN KEY ("session_id") REFERENCES "chat_sessions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "citations" ADD FOREIGN KEY ("chunk_id") REFERENCES "document_chunks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "citations" ADD FOREIGN KEY ("asset_id") REFERENCES "assets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "citations" ADD FOREIGN KEY ("tag_id") REFERENCES "sensor_tags" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "citations" ADD FOREIGN KEY ("hazop_row_id") REFERENCES "hazop_rows" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "citations" ADD FOREIGN KEY ("chat_message_id") REFERENCES "chat_messages" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "citations" ADD FOREIGN KEY ("proposal_id") REFERENCES "hazop_proposals" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "citations" ADD FOREIGN KEY ("approval_item_id") REFERENCES "approval_items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "citations" ADD FOREIGN KEY ("rescore_id") REFERENCES "risk_rescores" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "audit_log" ADD FOREIGN KEY ("actor_user") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "audit_log" ADD FOREIGN KEY ("replay_run_id") REFERENCES "replay_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "golden_items" ADD FOREIGN KEY ("authored_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "golden_items" ADD FOREIGN KEY ("reviewed_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "eval_runs" ADD FOREIGN KEY ("rule_set_id") REFERENCES "risk_rule_sets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "eval_results" ADD FOREIGN KEY ("eval_run_id") REFERENCES "eval_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "eval_item_results" ADD FOREIGN KEY ("eval_run_id") REFERENCES "eval_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "eval_item_results" ADD FOREIGN KEY ("golden_item_id") REFERENCES "golden_items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "eval_item_results" ADD FOREIGN KEY ("agent_run_id") REFERENCES "agent_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;
