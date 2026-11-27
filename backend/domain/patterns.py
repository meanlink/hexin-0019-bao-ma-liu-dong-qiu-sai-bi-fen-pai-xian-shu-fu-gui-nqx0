from core.errors import DomainError


def test_patterns(conn):
    rows = conn.execute(
        """
        SELECT name, expected_mask, current_target_ma, active, is_bad, bad,
               is_active, status, marked_bad_at, marked_bad_by, bad_reason,
               bad_roster_revision
        FROM lamp_pattern ORDER BY name
        """
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        active = bool(item["active"])
        item.update(
            {
                "pattern_name": item["name"],
                "state": "active" if active else "bad",
                "enabled": active,
                "usable": active,
                "disabled": not active,
                "is_disabled": not active,
                "quarantined": not active,
                "is_quarantined": not active,
            }
        )
        result.append(item)
    return result


def pattern_responses(conn, sweep_id, *, require_complete=True, scope="all"):
    """Return pattern rows for a sweep.

    scope="active" only returns the current classification roster.
    scope="recorded-active" returns active patterns plus bad patterns that
    were actually measured, preserving independent retest evidence.
    scope="all" is the complete fixture snapshot.
    """
    where = ""
    if scope == "active":
        where = "WHERE p.active"
    elif scope == "recorded-active":
        where = "WHERE p.active OR r.first_mask IS NOT NULL"
    rows = conn.execute(
        f"""
        SELECT p.name,p.expected_mask,p.current_target_ma,p.active,p.is_bad,p.status,
               r.first_mask,r.second_mask,r.settle_ms,r.current_ma
        FROM lamp_pattern AS p
        LEFT JOIN lamp_response AS r
          ON r.pattern_name=p.name AND r.sweep_id=%s
        {where}
        ORDER BY p.name
        """,
        (sweep_id,),
    ).fetchall()
    if require_complete:
        missing = [row["name"] for row in rows if row["first_mask"] is None]
        if not rows or missing:
            raise DomainError(409, f"incomplete fixture sweep; missing {', '.join(missing)}")
    return rows


def classification_responses(conn, sweep_id):
    return pattern_responses(conn, sweep_id, scope="active")


def blockers(rows, settle_limit):
    rejected = []
    for row in rows:
        expected = row["expected_mask"]
        tolerance = max(5, row["current_target_ma"] * 0.1)
        reasons = []
        if (row["first_mask"], row["second_mask"]) != (expected, expected):
            reasons.append("lamp layout differs from both expected scans")
        if row["settle_ms"] > settle_limit:
            reasons.append("settling exceeds board allowance")
        if abs(row["current_ma"] - row["current_target_ma"]) > tolerance:
            reasons.append("current remains outside fixture allowance")
        if reasons:
            rejected.append({"pattern": row["name"], "reasons": reasons})
    return rejected
