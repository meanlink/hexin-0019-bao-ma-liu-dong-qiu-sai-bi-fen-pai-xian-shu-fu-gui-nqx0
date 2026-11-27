from core.errors import DomainError

from .cards import card_details, lock_card
from .diagnosis import calculate, fault
from .dispositions import CANCELLED, EXEMPT, RESTORED, TERMINAL_OUTCOMES, latest_disposition_row
from .roster import current_pattern_revision
from .spare_handling import return_reserved_spare
from .sweeps import read_sweep


def _idempotency_key(spec, header_key=None):
    if header_key:
        return header_key
    if spec is None:
        return None
    return spec.idempotency_key or spec.key


def _existing_keyed_response(conn, key):
    if not key:
        return None
    row = conn.execute(
        "SELECT card_id FROM card_pattern_disposition WHERE idempotency_key=%s", (key,)
    ).fetchone()
    return card_details(conn, row["card_id"]) if row else None


def _ensure_row(conn, card, revision, idempotency_key=None):
    old = fault(conn, card["diagnosis_id"])
    conn.execute(
        """
        INSERT INTO card_pattern_disposition
            (card_id, pattern_revision, old_diagnosis_id, old_label, outcome,
             spare_serial, idempotency_key)
        VALUES (%s,%s,%s,%s,'pending',%s,%s)
        ON CONFLICT (card_id, pattern_revision) DO NOTHING
        """,
        (card["id"], revision, old["id"], old["label"], card["spare_serial"], idempotency_key),
    )
    row = conn.execute(
        "SELECT * FROM card_pattern_disposition WHERE card_id=%s AND pattern_revision=%s FOR UPDATE",
        (card["id"], revision),
    ).fetchone()
    if idempotency_key and not row["idempotency_key"]:
        conn.execute(
            "UPDATE card_pattern_disposition SET idempotency_key=%s WHERE id=%s AND idempotency_key IS NULL",
            (idempotency_key, row["id"]),
        )
        row = conn.execute("SELECT * FROM card_pattern_disposition WHERE id=%s", (row["id"],)).fetchone()
    return row


def _diagnosis_from_spec(conn, spec, old, revision):
    requested_id = None
    sample_revision = None
    if spec is not None:
        requested_id = (
            spec.diagnosis_id
            or spec.new_diagnosis_id
            or spec.reclassification_id
            or spec.result_id
        )
        sample_revision = spec.sample_revision

    if requested_id:
        new = fault(conn, requested_id)
    else:
        sweep = read_sweep(conn, old["sweep_id"])
        sample = sweep["sample_revision"] if sample_revision is None else sample_revision
        result = calculate(conn, old["sweep_id"], sample)
        new = fault(conn, result["diagnosis_id"])

    if new["id"] == old["id"]:
        raise DomainError(409, "provide a classification calculated under the latest pattern roster")
    if new.get("pattern_revision", 1) != revision:
        raise DomainError(409, "the replacement classification does not use the latest pattern roster")
    if new["sweep_id"] != old["sweep_id"]:
        raise DomainError(409, "reclassification must be performed on the original diagnostic sweep")

    sweep = read_sweep(conn, old["sweep_id"])
    if new["sample_revision"] != sweep["sample_revision"]:
        raise DomainError(409, "classification does not match the current diagnostic inputs")
    return new


def reassess_card(conn, card_id, spec=None, actor="system", *, idempotency_key=None):
    key = _idempotency_key(spec, idempotency_key)
    keyed = _existing_keyed_response(conn, key)
    if keyed is not None:
        return keyed

    # Board lock serializes with mark-pattern-bad and fitting.
    card = lock_card(conn, card_id)
    revision = current_pattern_revision(conn)

    if card["status"] == "fitted":
        conn.execute(
            """
            INSERT INTO card_pattern_disposition
                (card_id, pattern_revision, old_diagnosis_id, old_label, outcome,
                 spare_serial, processed_by, processed_at, classification_changed, note)
            SELECT %s,%s,c.diagnosis_id,d.label,'exempt',c.spare_serial,%s,now(),false,
                   'already fitted; independent retest remains required'
            FROM restoration_card c JOIN wire_diagnosis d ON d.id=c.diagnosis_id
            WHERE c.id=%s
            ON CONFLICT (card_id, pattern_revision) DO NOTHING
            """,
            (card_id, revision, actor, card_id),
        )
        return card_details(conn, card_id)

    if card["status"] in {"cancelled", "released"}:
        return card_details(conn, card_id)

    row = _ensure_row(conn, card, revision, key)
    if row["outcome"] in TERMINAL_OUTCOMES:
        return card_details(conn, card_id)

    old = fault(conn, card["diagnosis_id"])
    new = _diagnosis_from_spec(conn, spec, old, revision)
    note = spec.reason if spec is not None and spec.reason else None
    return apply_reclassification(conn, row, new, actor=actor, note=note)


def apply_reclassification(conn, row, new, *, actor="classifier", note=None):
    """Apply a fresh classification to one pending card disposition."""
    card_id = row["card_id"]
    if row["outcome"] in TERMINAL_OUTCOMES:
        return card_details(conn, card_id)

    card = lock_card(conn, card_id)
    if card["status"] == "fitted":
        conn.execute(
            """
            UPDATE card_pattern_disposition
            SET outcome='exempt', processed_by=%s, processed_at=now(),
                new_diagnosis_id=%s, new_label=%s, classification_changed=false
            WHERE id=%s AND outcome='pending'
            """,
            (actor, new["id"], new["label"], row["id"]),
        )
        return card_details(conn, card_id)
    if card["status"] != "allocated":
        return card_details(conn, card_id)

    old = fault(conn, row["old_diagnosis_id"] or card["diagnosis_id"])
    changed = old["label"] != new["label"]

    if changed:
        returned_now = return_reserved_spare(conn, card["spare_serial"])
        spare = None
        if card["spare_serial"]:
            spare = conn.execute(
                "SELECT state FROM spare_harness WHERE serial=%s", (card["spare_serial"],)
            ).fetchone()
        material_returned = bool(card["spare_serial"]) and (
            returned_now or (spare is not None and spare["state"] == "spare")
        )
        outcome = CANCELLED
        conn.execute(
            "UPDATE restoration_card SET status='cancelled' WHERE id=%s AND status='allocated'",
            (card_id,),
        )
        conn.execute(
            "UPDATE display_board SET release_state='check_due' WHERE code=%s",
            (card["board_code"],),
        )
    else:
        material_returned = bool(row["material_returned"])
        outcome = RESTORED
        # Keep restoration_card.diagnosis_id as the original audit basis; the
        # accepted replacement is stored in card_pattern_disposition.
        conn.execute(
            """
            UPDATE restoration_card SET status='allocated'
            WHERE id=%s AND status IN ('allocated','held','blocked','suspended')
            """,
            (card_id,),
        )
        conn.execute(
            "UPDATE display_board SET release_state='repairing' WHERE code=%s AND release_state='check_due'",
            (card["board_code"],),
        )

    conn.execute(
        """
        UPDATE card_pattern_disposition
        SET new_diagnosis_id=%s, new_label=%s, classification_changed=%s,
            outcome=%s, material_returned=%s, processed_by=%s, processed_at=now(),
            note=COALESCE(%s, note)
        WHERE id=%s
        """,
        (
            new["id"], new["label"], changed, outcome, material_returned,
            actor, note, row["id"],
        ),
    )
    return card_details(conn, card_id)


def apply_new_diagnosis_to_cards(conn, new):
    """Worker hook: dispose cards waiting for this sweep's latest classification."""
    revision = int(new.get("pattern_revision") or current_pattern_revision(conn))
    rows = conn.execute(
        """
        SELECT d.*
        FROM card_pattern_disposition d
        JOIN wire_diagnosis old ON old.id = d.old_diagnosis_id
        JOIN restoration_card c ON c.id = d.card_id
        WHERE d.pattern_revision=%s
          AND d.outcome='pending'
          AND c.status='allocated'
          AND old.sweep_id=%s
        ORDER BY d.card_id
        FOR UPDATE OF d
        """,
        (revision, new["sweep_id"]),
    ).fetchall()
    results = []
    for row in rows:
        results.append(apply_reclassification(conn, row, new))
    return results


def reassess_pending(conn, spec=None, actor="system", *, revision=None):
    if revision is None:
        revision = current_pattern_revision(conn)
    rows = conn.execute(
        """
        SELECT card_id FROM card_pattern_disposition
        WHERE pattern_revision=%s AND outcome='pending' ORDER BY card_id
        """,
        (revision,),
    ).fetchall()
    results = []
    for row in rows:
        results.append(reassess_card(conn, row["card_id"], spec, actor))
    return {
        "pattern_revision": revision,
        "roster_revision": revision,
        "processed": len(results),
        "cards": results,
        "results": results,
    }
