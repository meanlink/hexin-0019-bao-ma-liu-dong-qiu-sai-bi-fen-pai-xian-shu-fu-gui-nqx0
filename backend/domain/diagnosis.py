from psycopg.types.json import Jsonb

from core.errors import DomainError
from core.jobs import enqueue

from .feature_selection import classify
from .features import derive
from .patterns import classification_responses
from .reference_pack import reference_pack
from .roster import current_pattern_revision
from .sweep_rules import sweep_applicable
from .sweeps import current_sweep


def check_diagnostic(conn, sweep_id, sample_revision, *, allow_roster_reclassification=False):
    sweep, board = current_sweep(conn, sweep_id)
    if sweep["purpose"] != "diagnosis":
        raise DomainError(409, "calibration classifier requires a diagnostic sweep")
    if sweep["sample_revision"] != sample_revision:
        raise DomainError(409, "signal collection was edited; rerun diagnosis")

    try:
        sweep_applicable(board, "diagnosis")
    except DomainError:
        # A pattern roster retirement requires re-judging the same sweep while
        # its original, uninstalled restoration card keeps the board repairing.
        if not allow_roster_reclassification:
            raise
        if board["release_state"] != "repairing":
            raise
        revision = current_pattern_revision(conn)
        if revision <= 1:
            raise
        linked = conn.execute(
            """
            SELECT c.id,c.status
            FROM restoration_card c
            JOIN wire_diagnosis d ON d.id=c.diagnosis_id
            WHERE c.board_code=%s AND c.status='allocated' AND d.sweep_id=%s
            """,
            (board["code"], sweep_id),
        ).fetchone()
        if linked is None:
            raise
    return classification_responses(conn, sweep_id)


def request_diagnosis(conn, sweep_id, sample_revision):
    check_diagnostic(conn, sweep_id, sample_revision, allow_roster_reclassification=True)
    return enqueue(conn, "classify_lamp_pattern", {"sweep_id": sweep_id, "sample_revision": sample_revision})


def fault(conn, diagnosis_id):
    row = conn.execute("SELECT * FROM wire_diagnosis WHERE id=%s", (diagnosis_id,)).fetchone()
    if row is None:
        raise DomainError(404, "unknown lamp classifier result")
    result = dict(row)
    revision = int(result.get("pattern_revision") or 1)
    result["pattern_revision"] = revision
    result["roster_revision"] = revision
    result["pattern_list_revision"] = revision
    latest_revision = current_pattern_revision(conn)
    is_latest = revision == latest_revision
    result["latest_pattern_revision"] = latest_revision
    result["uses_latest_pattern_roster"] = is_latest
    result["is_current"] = is_latest
    result["current"] = is_latest
    result["valid"] = is_latest
    result["stale"] = not is_latest
    result["expired"] = not is_latest
    return result


def calculate(conn, sweep_id, sample_revision):
    readings = check_diagnostic(
        conn, sweep_id, sample_revision, allow_roster_reclassification=True
    )
    pattern_revision = current_pattern_revision(conn)
    stored = conn.execute(
        """
        SELECT id,label FROM wire_diagnosis
        WHERE sweep_id=%s AND sample_revision=%s AND pattern_revision=%s
        """,
        (sweep_id, sample_revision, pattern_revision),
    ).fetchone()
    result = None
    if stored:
        result = {"diagnosis_id": stored["id"], "label": stored["label"], "pattern_revision": pattern_revision}

    if result is None:
        features = derive(readings)
        label, metrics = classify(features, *reference_pack(conn))
        metrics = dict(metrics)
        metrics["pattern_revision"] = pattern_revision
        metrics["roster_revision"] = pattern_revision
        metrics["classification_patterns"] = [row["name"] for row in readings]
        inserted = conn.execute(
            """
            INSERT INTO wire_diagnosis(sweep_id,sample_revision,label,metrics,features,pattern_revision)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (sweep_id,sample_revision,pattern_revision) DO NOTHING
            RETURNING id
            """,
            (sweep_id, sample_revision, label, Jsonb(metrics), Jsonb(features), pattern_revision),
        ).fetchone()
        if inserted is None:
            stored = conn.execute(
                """
                SELECT id,label FROM wire_diagnosis
                WHERE sweep_id=%s AND sample_revision=%s AND pattern_revision=%s
                """,
                (sweep_id, sample_revision, pattern_revision),
            ).fetchone()
            result = {"diagnosis_id": stored["id"], "label": stored["label"], "pattern_revision": pattern_revision}
        else:
            result = {"diagnosis_id": inserted["id"], "label": label, "pattern_revision": pattern_revision}

    # The classifier is also the rejudgment event: resolve cards waiting for
    # this sweep under the current pattern roster.
    from .card_review import apply_new_diagnosis_to_cards

    apply_new_diagnosis_to_cards(conn, fault(conn, result["diagnosis_id"]))
    return result
