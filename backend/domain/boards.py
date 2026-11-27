from core.errors import DomainError


def load_board(conn, code, *, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    row = conn.execute("SELECT * FROM display_board WHERE code=%s" + suffix, (code,)).fetchone()
    if row is None:
        raise DomainError(404, "unknown traveling score board")
    return row


def crew_manifest(conn):
    return conn.execute(
        """
        SELECT b.code, b.label, b.harness_revision, s.meter_code AS retest_meter,
               rr.id AS road_release_id, rr.signed_at
        FROM display_board AS b
        JOIN restoration_card AS c ON c.board_code=b.code
        JOIN road_release AS rr ON rr.card_id=c.id
        JOIN lamp_sweep AS s ON s.id=rr.retest_id AND s.harness_revision=b.harness_revision
        WHERE b.release_state='ready' ORDER BY b.code
        """
    ).fetchall()


def spare_stock(conn):
    return conn.execute(
        "SELECT serial,bank_layout,state,fitted_board FROM spare_harness ORDER BY serial"
    ).fetchall()


def bench_status(conn):
    return conn.execute(
        "SELECT code,label,layout,harness_revision,release_state FROM display_board ORDER BY code"
    ).fetchall()
