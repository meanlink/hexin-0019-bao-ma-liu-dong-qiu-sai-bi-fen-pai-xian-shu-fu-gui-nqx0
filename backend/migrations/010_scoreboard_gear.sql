CREATE TABLE field_meter (
    code text PRIMARY KEY,
    station text NOT NULL,
    verified boolean NOT NULL DEFAULT true
);

CREATE TABLE display_board (
    code text PRIMARY KEY,
    label text NOT NULL,
    layout text NOT NULL CHECK (layout = '2x7'),
    harness_revision integer NOT NULL CHECK (harness_revision > 0),
    release_state text NOT NULL CHECK (release_state IN ('check_due','repairing','awaiting_retest','ready')),
    settle_limit_ms smallint NOT NULL CHECK (settle_limit_ms BETWEEN 1 AND 1000)
);

CREATE TABLE spare_harness (
    serial text PRIMARY KEY,
    bank_layout text NOT NULL CHECK (bank_layout IN ('2x7','1x7')),
    state text NOT NULL CHECK (state IN ('spare','reserved','fitted','retired')),
    fitted_board text REFERENCES display_board(code),
    CHECK ((fitted_board IS NOT NULL) = (state IN ('fitted','retired')))
);

CREATE UNIQUE INDEX one_fitted_spare_per_board ON spare_harness(fitted_board) WHERE state='fitted';
