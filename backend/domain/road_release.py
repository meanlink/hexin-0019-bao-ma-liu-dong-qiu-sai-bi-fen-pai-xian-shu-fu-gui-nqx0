from core.errors import DomainError

from .boards import load_board
from .cards import card_details, lock_card
from .patterns import blockers, pattern_responses
from .sweep_rules import checked_meter, independent_meter
from .sweeps import read_sweep


def release(conn, card_id, spec, reviewer):
    card = lock_card(conn, card_id)
    if card["status"] != "fitted" or card["release_state"] != "awaiting_retest":
        raise DomainError(409, "only a fitted and held board may return to crew stock")
    sweep = read_sweep(conn, spec.retest_id)
    if (sweep["board_code"], sweep["harness_revision"], sweep["purpose"]) != (
        card["board_code"], card["harness_revision"], "retest",
    ):
        raise DomainError(409, "retest must use the installed harness revision on this board")
    independent_meter(card, sweep["meter_code"], sweep["operator_name"])
    checked_meter(conn, sweep["meter_code"])
    if spec.sample_revision != sweep["sample_revision"]:
        raise DomainError(409, "retest readings changed after the signoff snapshot was selected")
    rows = pattern_responses(conn, sweep["id"], scope="recorded-active")
    board = load_board(conn, card["board_code"])
    failed = blockers(rows, board["settle_limit_ms"])
    if failed:
        pattern = failed[0]["pattern"]
        why = ", ".join(failed[0]["reasons"])
        raise DomainError(409, f"independent fixture did not clear {pattern}: {why}")
    conn.execute(
        "INSERT INTO road_release(card_id,retest_id,released_by) VALUES (%s,%s,%s)",
        (card_id, sweep["id"], reviewer),
    )
    conn.execute("UPDATE restoration_card SET status='released' WHERE id=%s", (card_id,))
    conn.execute("UPDATE display_board SET release_state='ready' WHERE code=%s", (card["board_code"],))
    return card_details(conn, card_id)
