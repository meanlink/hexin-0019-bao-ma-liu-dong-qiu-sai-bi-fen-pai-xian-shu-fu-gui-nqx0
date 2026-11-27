from core.errors import DomainError

from .diagnosis import calculate


def run(conn, kind, payload):
    if kind == "classify_lamp_pattern":
        return calculate(conn, payload["sweep_id"], payload["sample_revision"])
    raise DomainError(422, "unsupported lamp diagnostic task")
