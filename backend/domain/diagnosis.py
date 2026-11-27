from psycopg.types.json import Jsonb

from core.errors import DomainError
from core.jobs import enqueue

from .feature_selection import classify
from .features import derive
from .patterns import pattern_responses
from .reference_pack import reference_pack
from .sweep_rules import sweep_applicable
from .sweeps import current_sweep


def check_diagnostic(conn, sweep_id, sample_revision):
    sweep, board = current_sweep(conn, sweep_id)
    if sweep["purpose"] != "diagnosis":
        raise DomainError(409, "calibration classifier requires a diagnostic sweep")
    if sweep["sample_revision"] != sample_revision:
        raise DomainError(409, "signal collection was edited; rerun diagnosis")
    sweep_applicable(board, "diagnosis")
    return pattern_responses(conn, sweep_id)


def request_diagnosis(conn, sweep_id, sample_revision):
    check_diagnostic(conn, sweep_id, sample_revision)
    return enqueue(conn, "classify_lamp_pattern", {"sweep_id": sweep_id, "sample_revision": sample_revision})


def fault(conn, diagnosis_id):
    row = conn.execute("SELECT * FROM wire_diagnosis WHERE id=%s", (diagnosis_id,)).fetchone()
    if row is None:
        raise DomainError(404, "unknown lamp classifier result")
    return row


def calculate(conn, sweep_id, sample_revision):
    readings = check_diagnostic(conn, sweep_id, sample_revision)
    stored = conn.execute(
        "SELECT id,label FROM wire_diagnosis WHERE sweep_id=%s AND sample_revision=%s",
        (sweep_id, sample_revision),
    ).fetchone()
    if stored:
        return {"diagnosis_id": stored["id"], "label": stored["label"]}
    features = derive(readings)
    label, metrics = classify(features, *reference_pack(conn))
    stored = conn.execute(
        """
        INSERT INTO wire_diagnosis(sweep_id,sample_revision,label,metrics,features)
        VALUES (%s,%s,%s,%s,%s) RETURNING id
        """,
        (sweep_id, sample_revision, label, Jsonb(metrics), Jsonb(features)),
    ).fetchone()
    return {"diagnosis_id": stored["id"], "label": label}
