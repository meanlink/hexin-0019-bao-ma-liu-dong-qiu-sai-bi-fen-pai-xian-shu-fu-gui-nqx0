from core.errors import DomainError
from core.jobs import enqueue

from .patterns import test_patterns

ROSTER_LOCK = 884302
INITIAL_REVISION = 1


def lock_roster(conn):
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (ROSTER_LOCK,))


def current_pattern_revision(conn):
    row = conn.execute("SELECT COALESCE(MAX(revision), 1) AS revision FROM pattern_roster_revision").fetchone()
    return int(row["revision"])


def roster_summary(conn):
    revision = current_pattern_revision(conn)
    rows = conn.execute(
        """
        SELECT revision, marked_pattern, reason, marked_by, created_at
        FROM pattern_roster_revision ORDER BY revision
        """
    ).fetchall()
    patterns = test_patterns(conn)
    active_names = [row["name"] for row in patterns if row["active"]]
    bad_names = [row["name"] for row in patterns if not row["active"]]
    return {
        "pattern_revision": revision,
        "roster_revision": revision,
        "pattern_list_revision": revision,
        "revision": revision,
        "pattern_count": len(active_names),
        "active_pattern_count": len(active_names),
        "active_patterns": active_names,
        "patterns": [dict(row) for row in patterns],
        "bad_patterns": bad_names,
        "excluded_patterns": bad_names,
        "revisions": [dict(row) for row in rows],
    }


def get_pattern(conn, name, *, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    row = conn.execute("SELECT * FROM lamp_pattern WHERE name=%s" + suffix, (name,)).fetchone()
    if row is None:
        raise DomainError(404, "unknown lamp pattern")
    return row


def mark_pattern_bad(conn, name, actor, reason=None):
    """Exclude a pattern and create pending work for uninstalled cards."""
    lock_roster(conn)
    pattern = get_pattern(conn, name, lock=True)

    if not pattern["active"]:
        revision = pattern["bad_roster_revision"] or current_pattern_revision(conn)
        event = conn.execute(
            "SELECT * FROM pattern_roster_revision WHERE marked_pattern=%s ORDER BY revision DESC LIMIT 1",
            (name,),
        ).fetchone()
        affected = conn.execute(
            "SELECT card_id AS id FROM card_pattern_disposition WHERE pattern_revision=%s ORDER BY card_id",
            (revision,),
        ).fetchall()
        return {
            **roster_summary(conn),
            "pattern": name,
            "marked_pattern": name,
            "pattern_name": name,
            "name": name,
            "already_bad": True,
            "idempotent": True,
            "pattern_revision_changed": False,
            "revision": current_pattern_revision(conn),
            "marked_revision": revision,
            "event": dict(event) if event else None,
            "affected_card_ids": [row["id"] for row in affected],
        }

    # Lock boards first, in code order.  Card fitting also takes the board
    # row lock first, so mark-bad and fit are serialized rather than racing.
    board_codes = [
        row["board_code"]
        for row in conn.execute(
            """
            SELECT DISTINCT board_code FROM restoration_card
            WHERE status = 'allocated' ORDER BY board_code
            """
        ).fetchall()
    ]
    from .boards import load_board

    for board_code in board_codes:
        load_board(conn, board_code, lock=True)

    conn.execute(
        """
        SELECT id FROM restoration_card WHERE status='allocated' ORDER BY id FOR UPDATE
        """
    ).fetchall()

    next_revision = int(
        conn.execute("SELECT COALESCE(MAX(revision), 0) + 1 AS next_revision FROM pattern_roster_revision")
        .fetchone()["next_revision"]
    )
    event = conn.execute(
        """
        INSERT INTO pattern_roster_revision
            (revision, marked_pattern, reason, marked_by)
        OVERRIDING SYSTEM VALUE
        VALUES (%s,%s,%s,%s) RETURNING *
        """,
        (next_revision, name, reason, actor),
    ).fetchone()
    conn.execute(
        """
        UPDATE lamp_pattern
        SET active=false, marked_bad_at=now(), marked_bad_by=%s,
            bad_reason=%s, bad_roster_revision=%s
        WHERE name=%s
        """,
        (actor, reason, next_revision, name),
    )

    affected = conn.execute(
        """
        INSERT INTO card_pattern_disposition
            (card_id, pattern_revision, marked_pattern, old_diagnosis_id, old_label,
             outcome, spare_serial)
        SELECT c.id, %s, %s, c.diagnosis_id, d.label, 'pending', c.spare_serial
        FROM restoration_card c
        JOIN wire_diagnosis d ON d.id = c.diagnosis_id
        WHERE c.status = 'allocated'
        ON CONFLICT (card_id, pattern_revision) DO NOTHING
        RETURNING card_id AS id
        """,
        (next_revision, name),
    ).fetchall()

    rejudgments = conn.execute(
        """
        SELECT DISTINCT d.sweep_id, d.sample_revision
        FROM card_pattern_disposition AS p
        JOIN wire_diagnosis AS d ON d.id = p.old_diagnosis_id
        WHERE p.pattern_revision = %s
        """,
        (next_revision,),
    ).fetchall()
    jobs = []
    for item in rejudgments:
        jobs.append(
            enqueue(
                conn,
                "classify_lamp_pattern",
                {
                    "sweep_id": item["sweep_id"],
                    "sample_revision": item["sample_revision"],
                    "pattern_revision": next_revision,
                },
            )
        )

    summary = roster_summary(conn)
    return {
        **summary,
        "pattern": name,
        "marked_pattern": name,
        "pattern_name": name,
        "name": name,
        "already_bad": False,
        "idempotent": False,
        "pattern_revision_changed": True,
        "marked_revision": next_revision,
        "event": dict(event),
        "affected_card_ids": [row["id"] for row in affected],
        "held_card_ids": [row["id"] for row in affected],
        "rejudgment_jobs": jobs,
        "jobs": jobs,
    }
