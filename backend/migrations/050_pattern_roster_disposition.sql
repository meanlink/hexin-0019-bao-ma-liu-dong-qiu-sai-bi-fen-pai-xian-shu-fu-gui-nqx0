-- Pattern roster revisions. Revision 1 is the original six-pattern roster.
CREATE TABLE pattern_roster_revision (
    revision smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK (revision > 0),
    marked_pattern text REFERENCES lamp_pattern(name),
    reason text,
    marked_by text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- The identity column starts at 1; insert the baseline roster explicitly.
INSERT INTO pattern_roster_revision(revision) OVERRIDING SYSTEM VALUE VALUES (1)
ON CONFLICT (revision) DO NOTHING;
SELECT setval(pg_get_serial_sequence('pattern_roster_revision', 'revision'), 1, true);

ALTER TABLE lamp_pattern ADD COLUMN active boolean NOT NULL DEFAULT true;
ALTER TABLE lamp_pattern ADD COLUMN marked_bad_at timestamptz;
ALTER TABLE lamp_pattern ADD COLUMN marked_bad_by text;
ALTER TABLE lamp_pattern ADD COLUMN bad_reason text;
ALTER TABLE lamp_pattern ADD COLUMN bad_roster_revision smallint;
ALTER TABLE lamp_pattern
    ADD COLUMN is_bad boolean GENERATED ALWAYS AS (NOT active) STORED;
ALTER TABLE lamp_pattern
    ADD COLUMN bad boolean GENERATED ALWAYS AS (NOT active) STORED;
ALTER TABLE lamp_pattern
    ADD COLUMN is_active boolean GENERATED ALWAYS AS (active) STORED;
ALTER TABLE lamp_pattern
    ADD COLUMN status text GENERATED ALWAYS AS (
        CASE WHEN active THEN 'active' ELSE 'bad' END
    ) STORED;

ALTER TABLE wire_diagnosis
    ADD COLUMN pattern_revision smallint NOT NULL DEFAULT 1
    CHECK (pattern_revision > 0);
ALTER TABLE wire_diagnosis
    ADD COLUMN roster_revision smallint GENERATED ALWAYS AS (pattern_revision) STORED;
ALTER TABLE wire_diagnosis
    ADD COLUMN pattern_list_revision smallint GENERATED ALWAYS AS (pattern_revision) STORED;
ALTER TABLE wire_diagnosis
    ADD COLUMN pattern_set_revision smallint GENERATED ALWAYS AS (pattern_revision) STORED;
ALTER TABLE wire_diagnosis
    ADD COLUMN active_pattern_revision smallint GENERATED ALWAYS AS (pattern_revision) STORED;

-- A sweep/sample can now have one classification for every pattern roster.
DO $$
DECLARE
    constraint_name text;
BEGIN
    FOR constraint_name IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'wire_diagnosis'
          AND c.contype = 'u'
          AND pg_get_constraintdef(c.oid) LIKE '%sweep_id%sample_revision%'
          AND pg_get_constraintdef(c.oid) NOT LIKE '%pattern_revision%'
    LOOP
        EXECUTE 'ALTER TABLE wire_diagnosis DROP CONSTRAINT ' || quote_ident(constraint_name);
    END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS wire_diagnosis_roster_uq
    ON wire_diagnosis(sweep_id, sample_revision, pattern_revision);

-- One disposition per card and roster revision makes retries idempotent.
CREATE TABLE card_pattern_disposition (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    card_id bigint NOT NULL REFERENCES restoration_card(id),
    pattern_revision smallint NOT NULL CHECK (pattern_revision > 0),
    marked_pattern text REFERENCES lamp_pattern(name),
    old_diagnosis_id bigint REFERENCES wire_diagnosis(id),
    old_label text CHECK (old_label IS NULL OR old_label IN ('normal','contact_drift','mapping_shift')),
    new_diagnosis_id bigint REFERENCES wire_diagnosis(id),
    new_label text CHECK (new_label IS NULL OR new_label IN ('normal','contact_drift','mapping_shift')),
    classification_changed boolean,
    outcome text NOT NULL DEFAULT 'pending'
        CHECK (outcome IN ('pending','restored','cancelled','exempt')),
    idempotency_key text UNIQUE,
    spare_serial text,
    material_returned boolean NOT NULL DEFAULT false,
    processed_by text,
    note text,
    disposition text GENERATED ALWAYS AS (outcome) STORED,
    result text GENERATED ALWAYS AS (outcome) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    UNIQUE (card_id, pattern_revision)
);

CREATE INDEX card_pattern_disposition_card_idx
    ON card_pattern_disposition(card_id, pattern_revision DESC);
CREATE INDEX card_pattern_disposition_pending_idx
    ON card_pattern_disposition(pattern_revision)
    WHERE outcome = 'pending';
