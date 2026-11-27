from core.errors import DomainError


def current_card(conn, board_code):
    return conn.execute(
        "SELECT * FROM restoration_card WHERE board_code=%s AND status IN ('allocated','fitted')",
        (board_code,),
    ).fetchone()


def sweep_applicable(board, purpose):
    if purpose == "retest" and board["release_state"] != "awaiting_retest":
        raise DomainError(409, "a fitted restoration card is required before a retest")
    if purpose == "diagnosis" and board["release_state"] not in {"check_due", "ready"}:
        raise DomainError(409, "finish or cancel the current restoration before diagnosing again")


def checked_meter(conn, meter_code):
    meter = conn.execute("SELECT * FROM field_meter WHERE code=%s", (meter_code,)).fetchone()
    if not meter or not meter["verified"]:
        raise DomainError(409, "use a registered and currently verified meter")
    return meter


def independent_meter(card, meter_code, operator_name):
    if meter_code == card["source_meter"]:
        raise DomainError(409, "restoration requires a different meter")
    if operator_name == card["source_operator"]:
        raise DomainError(403, "the technician who diagnosed the board cannot conduct the retest")
