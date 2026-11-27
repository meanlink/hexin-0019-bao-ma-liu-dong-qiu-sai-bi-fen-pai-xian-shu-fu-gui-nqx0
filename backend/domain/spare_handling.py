from core.errors import DomainError


def reserve_spare(conn, serial, layout):
    spare = conn.execute("SELECT * FROM spare_harness WHERE serial=%s FOR UPDATE", (serial,)).fetchone()
    if not spare or spare["state"] != "spare" or spare["bank_layout"] != layout:
        raise DomainError(409, "spare must be available and match the board bank layout")
    conn.execute("UPDATE spare_harness SET state='reserved' WHERE serial=%s", (serial,))


def return_to_stock(conn, serial):
    return return_reserved_spare(conn, serial)


def return_reserved_spare(conn, serial):
    """Return one reserved serial; return True only when this call moves it."""
    if not serial:
        return False
    row = conn.execute(
        "UPDATE spare_harness SET state='spare' WHERE serial=%s AND state='reserved' RETURNING serial",
        (serial,),
    ).fetchone()
    return row is not None


def fit_spare(conn, serial, board_code):
    spare = conn.execute("SELECT * FROM spare_harness WHERE serial=%s FOR UPDATE", (serial,)).fetchone()
    if not spare or spare["state"] != "reserved":
        raise DomainError(409, "allocated spare is no longer in the reservation tray")
    conn.execute(
        "UPDATE spare_harness SET state='retired' WHERE fitted_board=%s AND state='fitted'", (board_code,)
    )
    conn.execute(
        "UPDATE spare_harness SET state='fitted',fitted_board=%s WHERE serial=%s", (board_code, serial)
    )
