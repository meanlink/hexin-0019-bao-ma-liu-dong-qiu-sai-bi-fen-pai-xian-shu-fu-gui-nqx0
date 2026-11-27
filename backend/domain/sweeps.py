from core.errors import DomainError

from .boards import load_board
from .sweep_rules import checked_meter, current_card, independent_meter, sweep_applicable


def read_sweep(conn, sweep_id):
    row = conn.execute("SELECT * FROM lamp_sweep WHERE id=%s", (sweep_id,)).fetchone()
    if row is None:
        raise DomainError(404, "unknown lamp sweep")
    return row


def current_sweep(conn, sweep_id):
    sweep = read_sweep(conn, sweep_id)
    board = load_board(conn, sweep["board_code"], lock=True)
    sweep = read_sweep(conn, sweep_id)
    if sweep["harness_revision"] != board["harness_revision"]:
        raise DomainError(409, "sweep belongs to a prior harness revision")
    return sweep, board


def begin_sweep(conn, board_code, spec, operator):
    board = load_board(conn, board_code, lock=True)
    if board["harness_revision"] != spec.harness_revision:
        raise DomainError(409, "submitted harness revision is no longer installed")
    checked_meter(conn, spec.meter_code)
    sweep_applicable(board, spec.purpose.value)
    if spec.purpose.value == "retest":
        independent_meter(current_card(conn, board_code), spec.meter_code, operator)
    return conn.execute(
        """
        INSERT INTO lamp_sweep(board_code,harness_revision,meter_code,operator_name,purpose)
        VALUES (%s,%s,%s,%s,%s) RETURNING *
        """,
        (board_code, spec.harness_revision, spec.meter_code, operator, spec.purpose.value),
    ).fetchone()


def record_signal(conn, sweep_id, signal, operator):
    sweep, board = current_sweep(conn, sweep_id)
    sweep_applicable(board, sweep["purpose"])
    if sweep["operator_name"] != operator:
        raise DomainError(403, "only the designated meter operator can record this sweep")
    if not conn.execute("SELECT 1 FROM lamp_pattern WHERE name=%s", (signal.pattern_name,)).fetchone():
        raise DomainError(409, "pattern does not belong to the lamp-test fixture")
    conn.execute(
        """
        INSERT INTO lamp_response (sweep_id,pattern_name,first_mask,second_mask,settle_ms,current_ma)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sweep_id,pattern_name) DO UPDATE SET first_mask=excluded.first_mask,
          second_mask=excluded.second_mask, settle_ms=excluded.settle_ms,current_ma=excluded.current_ma
        """,
        (sweep_id, signal.pattern_name, signal.first_mask, signal.second_mask,
         signal.settle_ms, signal.current_ma),
    )
    return conn.execute(
        "UPDATE lamp_sweep SET sample_revision=sample_revision+1 WHERE id=%s RETURNING *", (sweep_id,)
    ).fetchone()
