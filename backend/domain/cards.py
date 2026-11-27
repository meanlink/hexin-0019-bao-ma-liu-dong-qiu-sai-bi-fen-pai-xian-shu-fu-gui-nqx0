from core.errors import DomainError

from .boards import load_board
from .diagnosis import fault
from .spare_handling import fit_spare, reserve_spare, return_to_stock
from .sweeps import current_sweep


def card_details(conn, card_id):
    card = conn.execute(
        """
        SELECT c.*,b.harness_revision,b.release_state,rr.id AS road_release_id
        FROM restoration_card AS c JOIN display_board AS b ON b.code=c.board_code
        LEFT JOIN road_release AS rr ON rr.card_id=c.id WHERE c.id=%s
        """,
        (card_id,),
    ).fetchone()
    if card is None:
        raise DomainError(404, "unknown restoration card")
    return card


def lock_card(conn, card_id):
    first = card_details(conn, card_id)
    load_board(conn, first["board_code"], lock=True)
    return card_details(conn, card_id)


def allocate_card(conn, board_code, draft):
    result = fault(conn, draft.diagnosis_id)
    sweep, board = current_sweep(conn, result["sweep_id"])
    if sweep["board_code"] != board_code or sweep["sample_revision"] != result["sample_revision"]:
        raise DomainError(409, "classification does not match the current diagnostic inputs")
    if board["release_state"] not in {"check_due", "ready"}:
        raise DomainError(409, "another restoration already controls this board")
    if result["label"] == "normal":
        raise DomainError(409, "a normal classifier result cannot reserve a harness restoration")
    if result["label"] == "mapping_shift" and draft.mode.value != "swap":
        raise DomainError(409, "a shifted bank map requires a matching replacement harness")
    if (draft.mode.value == "swap") != (draft.spare_serial is not None):
        raise DomainError(409, "swap requires one spare; reseat does not reserve stock")
    if draft.spare_serial:
        reserve_spare(conn, draft.spare_serial, board["layout"])
    card = conn.execute(
        """
        INSERT INTO restoration_card(board_code,diagnosis_id,diagnosed_revision,mode,spare_serial,source_meter,
                                     source_operator,status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'allocated') ON CONFLICT DO NOTHING RETURNING id
        """,
        (board_code, result["id"], board["harness_revision"], draft.mode.value,
         draft.spare_serial, sweep["meter_code"], sweep["operator_name"]),
    ).fetchone()
    if not card:
        raise DomainError(409, "diagnostic result has already been used for a restoration")
    conn.execute("UPDATE display_board SET release_state='repairing' WHERE code=%s", (board_code,))
    return card_details(conn, card["id"])


def fit(conn, card_id, note):
    card = lock_card(conn, card_id)
    if card["status"] != "allocated" or card["diagnosed_revision"] != card["harness_revision"]:
        raise DomainError(409, "only a current allocated card can be fitted")
    if card["spare_serial"]:
        fit_spare(conn, card["spare_serial"], card["board_code"])
    conn.execute(
        "UPDATE restoration_card SET status='fitted',installation_note=%s WHERE id=%s", (note, card_id)
    )
    conn.execute(
        """
        UPDATE display_board SET release_state='awaiting_retest',harness_revision=harness_revision+1
        WHERE code=%s
        """,
        (card["board_code"],),
    )
    return card_details(conn, card_id)


def cancel(conn, card_id):
    card = lock_card(conn, card_id)
    if card["status"] != "allocated":
        raise DomainError(409, "a fitted card cannot be cancelled; it requires independent retest")
    if card["spare_serial"]:
        return_to_stock(conn, card["spare_serial"])
    conn.execute("UPDATE restoration_card SET status='cancelled' WHERE id=%s", (card_id,))
    conn.execute("UPDATE display_board SET release_state='check_due' WHERE code=%s", (card["board_code"],))
    return card_details(conn, card_id)
