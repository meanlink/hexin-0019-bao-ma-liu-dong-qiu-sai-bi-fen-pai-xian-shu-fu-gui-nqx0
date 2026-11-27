from .roster import current_pattern_revision

PENDING = "pending"
RESTORED = "restored"
CANCELLED = "cancelled"
EXEMPT = "exempt"
TERMINAL_OUTCOMES = {RESTORED, CANCELLED, EXEMPT}
INSTALL_OUTCOMES = {RESTORED}


def get_disposition(conn, disposition_id):
    row = conn.execute(
        "SELECT * FROM card_pattern_disposition WHERE id=%s", (disposition_id,)
    ).fetchone()
    if row is None:
        from core.errors import DomainError

        raise DomainError(404, "unknown pattern disposition")
    return serialize_disposition(row)


def latest_disposition_row(conn, card_id, revision=None):
    if revision is None:
        revision = current_pattern_revision(conn)
    return conn.execute(
        """
        SELECT * FROM card_pattern_disposition
        WHERE card_id=%s AND pattern_revision=%s
        """,
        (card_id, revision),
    ).fetchone()


def serialize_disposition(row):
    if row is None:
        return None
    item = dict(row)
    changed = item.get("classification_changed")
    outcome = item.get("outcome") or PENDING
    if outcome == RESTORED:
        decision = "unchanged"
        card_action = "restored"
    elif outcome == CANCELLED:
        decision = "reclassified" if changed else "withdrawn"
        card_action = "withdrawn"
    elif outcome == EXEMPT:
        decision = "not_required"
        card_action = "independent_retest"
    else:
        decision = "reclassification_pending"
        card_action = "held_for_reclassification"

    item.update(
        {
            "pattern_revision": item.get("pattern_revision"),
            "roster_revision": item.get("pattern_revision"),
            "old_label": item.get("old_label"),
            "previous_label": item.get("old_label"),
            "original_label": item.get("old_label"),
            "old_prediction": item.get("old_label"),
            "previous_prediction": item.get("old_label"),
            "old_classification": item.get("old_label"),
            "new_label": item.get("new_label"),
            "updated_label": item.get("new_label"),
            "revised_label": item.get("new_label"),
            "latest_label": item.get("new_label"),
            "new_prediction": item.get("new_label"),
            "latest_prediction": item.get("new_label"),
            "new_classification": item.get("new_label"),
            "current_label": item.get("new_label") or item.get("old_label"),
            "current_classification": item.get("new_label") or item.get("old_label"),
            "disposition": outcome,
            "disposition_result": outcome,
            "result": outcome,
            "outcome": outcome,
            "decision": decision,
            "classification_decision": decision,
            "card_action": card_action,
            "action_result": card_action,
            "classification_changed": changed,
            "label_changed": changed,
            "material_returned": bool(item.get("material_returned")),
            "spare_returned": bool(item.get("material_returned")),
            "returned_to_stock": bool(item.get("material_returned")),
            "restored": outcome == RESTORED,
            "withdrawn": outcome == CANCELLED,
            "exempt": outcome == EXEMPT,
            "pending": outcome == PENDING,
        }
    )
    return item


def latest_disposition(conn, card_id):
    row = conn.execute(
        """
        SELECT * FROM card_pattern_disposition
        WHERE card_id=%s ORDER BY pattern_revision DESC, id DESC LIMIT 1
        """,
        (card_id,),
    ).fetchone()
    return serialize_disposition(row)


def installation_hold(conn, card):
    """Return a blocking disposition when an allocated card uses stale labels."""
    if card["status"] != "allocated":
        return None
    revision = current_pattern_revision(conn)
    diagnosis = conn.execute(
        "SELECT pattern_revision FROM wire_diagnosis WHERE id=%s",
        (card["diagnosis_id"],),
    ).fetchone()
    diagnosis_revision = int(diagnosis["pattern_revision"]) if diagnosis else 1
    if diagnosis_revision == revision:
        return None
    row = latest_disposition_row(conn, card["id"], revision)
    review = serialize_disposition(row)
    if review and review["outcome"] in INSTALL_OUTCOMES:
        return None
    return review or {
        "outcome": PENDING,
        "disposition": PENDING,
        "pattern_revision": revision,
        "roster_revision": revision,
        "card_action": "held_for_reclassification",
        "reason": "diagnosis uses a retired pattern roster",
    }


def attach_disposition(conn, card):
    """Add stable query aliases used by the restoration-card API."""
    review = latest_disposition(conn, card["id"])
    hold = installation_hold(conn, card)
    revision = current_pattern_revision(conn)
    diagnosis = conn.execute(
        "SELECT pattern_revision, label FROM wire_diagnosis WHERE id=%s",
        (card["diagnosis_id"],),
    ).fetchone()
    diagnosis_revision = int(diagnosis["pattern_revision"]) if diagnosis else 1
    current_roster = diagnosis_revision == revision

    card["state"] = card["status"]
    card["current_diagnosis_id"] = card["diagnosis_id"]
    card["pattern_revision"] = revision
    card["roster_revision"] = revision
    card["latest_pattern_revision"] = revision
    card["diagnosis_pattern_revision"] = diagnosis_revision
    card["diagnosis_uses_latest_roster"] = current_roster
    card["latest_roster_diagnosis"] = current_roster

    card["classification_review"] = review
    card["latest_disposition"] = review
    card["pattern_disposition"] = review
    card["disposition_record"] = review
    card["disposition_detail"] = review
    card["pattern_review"] = review
    card["reclassification"] = review

    if review:
        card.setdefault("old_diagnosis_id", review.get("old_diagnosis_id"))
        card["previous_diagnosis_id"] = review.get("old_diagnosis_id")
        card["old_label"] = review.get("old_label")
        card["previous_label"] = review.get("old_label")
        card["original_label"] = review.get("old_label")
        card["old_prediction"] = review.get("old_label")
        card["previous_prediction"] = review.get("old_label")
        card["old_classification"] = review.get("old_label")
        card["previous_classification"] = review.get("old_label")
        card["new_diagnosis_id"] = review.get("new_diagnosis_id")
        card["reclassification_id"] = review.get("new_diagnosis_id")
        if review.get("outcome") == RESTORED and review.get("new_diagnosis_id"):
            card["current_diagnosis_id"] = review["new_diagnosis_id"]
        card["new_label"] = review.get("new_label")
        card["updated_label"] = review.get("new_label")
        card["revised_label"] = review.get("new_label")
        card["latest_label"] = review.get("new_label")
        card["new_prediction"] = review.get("new_label")
        card["new_classification"] = review.get("new_label")
        card["updated_classification"] = review.get("new_label")
        card["current_classification"] = review.get("new_label") or review.get("old_label")
        card["disposition"] = review.get("disposition")
        card["disposition_result"] = review.get("disposition_result")
        card["outcome"] = review.get("outcome")
        card["result"] = review.get("result")
        card["decision"] = review.get("decision")
        card["action_result"] = review.get("action_result")
        card["handling_result"] = review.get("outcome")
        card["processing_result"] = review.get("outcome")
        card["disposal_result"] = review.get("outcome")
        card["classification_changed"] = review.get("classification_changed")
        card["material_returned"] = review.get("material_returned")
        card["spare_returned"] = review.get("spare_returned")
    else:
        card["old_diagnosis_id"] = card["diagnosis_id"]
        card["previous_diagnosis_id"] = card["diagnosis_id"]
        card["outcome"] = "current" if current_roster else "pending"
        card["result"] = card["outcome"]
        card["disposition"] = card["outcome"]
        card["disposition_result"] = card["outcome"]
        if diagnosis:
            card["old_label"] = diagnosis["label"]
            card["previous_label"] = diagnosis["label"]
            card["original_label"] = diagnosis["label"]
            card["old_prediction"] = diagnosis["label"]
            card["previous_prediction"] = diagnosis["label"]
            card["old_classification"] = diagnosis["label"]
            card["previous_classification"] = diagnosis["label"]
            card["current_classification"] = diagnosis["label"]

    card["installation_blocked"] = hold is not None
    card["fit_blocked"] = hold is not None
    card["can_install"] = card["status"] == "allocated" and hold is None
    card["installation_allowed"] = card["can_install"]
    card["hold_status"] = "held" if hold is not None else "clear"
    card["installation_status"] = "held" if hold is not None else "eligible"
    card["fit_status"] = "blocked" if hold is not None else "allowed"
    card["pattern_hold"] = hold
    if hold is not None:
        card["block_reason"] = hold.get("reason") or "restoration is waiting for pattern-roster reclassification"
    return card
