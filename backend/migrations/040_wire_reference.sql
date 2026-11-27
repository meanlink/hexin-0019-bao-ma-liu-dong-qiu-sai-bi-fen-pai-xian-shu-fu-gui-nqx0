CREATE TABLE reference_trace (
    specimen text NOT NULL,
    scan_group smallint NOT NULL CHECK (scan_group > 0),
    label text NOT NULL CHECK (label IN ('normal','contact_drift','mapping_shift')),
    pattern_name text NOT NULL REFERENCES lamp_pattern(name),
    first_mask smallint NOT NULL CHECK (first_mask BETWEEN 0 AND 16383),
    second_mask smallint NOT NULL CHECK (second_mask BETWEEN 0 AND 16383),
    settle_ms smallint NOT NULL CHECK (settle_ms BETWEEN 0 AND 2000),
    current_ma smallint NOT NULL CHECK (current_ma BETWEEN 0 AND 2000),
    PRIMARY KEY (specimen, pattern_name)
);
