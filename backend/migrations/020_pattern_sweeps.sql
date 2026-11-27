CREATE TABLE lamp_pattern (
    name text PRIMARY KEY,
    expected_mask smallint NOT NULL CHECK (expected_mask BETWEEN 0 AND 16383),
    current_target_ma smallint NOT NULL CHECK (current_target_ma BETWEEN 0 AND 2000)
);

CREATE TABLE lamp_sweep (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    board_code text NOT NULL REFERENCES display_board(code),
    harness_revision integer NOT NULL CHECK (harness_revision > 0),
    meter_code text NOT NULL REFERENCES field_meter(code),
    operator_name text NOT NULL,
    purpose text NOT NULL CHECK (purpose IN ('diagnosis','retest')),
    sample_revision integer NOT NULL DEFAULT 0 CHECK (sample_revision >= 0),
    started_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE lamp_response (
    sweep_id bigint NOT NULL REFERENCES lamp_sweep(id),
    pattern_name text NOT NULL REFERENCES lamp_pattern(name),
    first_mask smallint NOT NULL CHECK (first_mask BETWEEN 0 AND 16383),
    second_mask smallint NOT NULL CHECK (second_mask BETWEEN 0 AND 16383),
    settle_ms smallint NOT NULL CHECK (settle_ms BETWEEN 0 AND 2000),
    current_ma smallint NOT NULL CHECK (current_ma BETWEEN 0 AND 2000),
    PRIMARY KEY (sweep_id, pattern_name)
);
