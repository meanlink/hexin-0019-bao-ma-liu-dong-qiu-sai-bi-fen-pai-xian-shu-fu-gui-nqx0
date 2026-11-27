from core.errors import DomainError


def test_patterns(conn):
    return conn.execute(
        "SELECT name,expected_mask,current_target_ma FROM lamp_pattern ORDER BY name"
    ).fetchall()


def pattern_responses(conn, sweep_id, *, require_complete=True):
    rows = conn.execute(
        """
        SELECT p.name,p.expected_mask,p.current_target_ma,r.first_mask,r.second_mask,r.settle_ms,r.current_ma
        FROM lamp_pattern AS p LEFT JOIN lamp_response AS r ON r.pattern_name=p.name AND r.sweep_id=%s
        ORDER BY p.name
        """,
        (sweep_id,),
    ).fetchall()
    if require_complete:
        missing = [row["name"] for row in rows if row["first_mask"] is None]
        if not rows or missing:
            raise DomainError(409, f"incomplete fixture sweep; missing {', '.join(missing)}")
    return rows


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
