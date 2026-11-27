CREATE TABLE wire_diagnosis (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sweep_id bigint NOT NULL REFERENCES lamp_sweep(id),
    sample_revision integer NOT NULL CHECK (sample_revision > 0),
    label text NOT NULL CHECK (label IN ('normal','contact_drift','mapping_shift')),
    metrics jsonb NOT NULL,
    features jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sweep_id, sample_revision)
);

CREATE TABLE restoration_card (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    board_code text NOT NULL REFERENCES display_board(code),
    diagnosis_id bigint NOT NULL UNIQUE REFERENCES wire_diagnosis(id),
    diagnosed_revision integer NOT NULL CHECK (diagnosed_revision > 0),
    mode text NOT NULL CHECK (mode IN ('reseat','swap')),
    spare_serial text REFERENCES spare_harness(serial),
    source_meter text NOT NULL REFERENCES field_meter(code),
    source_operator text NOT NULL,
    status text NOT NULL CHECK (status IN ('allocated','fitted','released','cancelled')),
    installation_note text,
    CHECK ((mode = 'swap') = (spare_serial IS NOT NULL))
);

CREATE UNIQUE INDEX one_current_repair_per_board ON restoration_card(board_code)
WHERE status IN ('allocated','fitted');

CREATE UNIQUE INDEX one_allocated_spare ON restoration_card(spare_serial)
WHERE spare_serial IS NOT NULL AND status = 'allocated';

CREATE TABLE road_release (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    card_id bigint NOT NULL UNIQUE REFERENCES restoration_card(id),
    retest_id bigint NOT NULL UNIQUE REFERENCES lamp_sweep(id),
    released_by text NOT NULL,
    signed_at timestamptz NOT NULL DEFAULT now()
);
