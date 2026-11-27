from fastapi import APIRouter, Depends, Header

from core.access import allow
from core.db import transaction
from core.errors import DomainError

from .card_input import ReassessInput
from .card_review import reassess_card
from .diagnosis import fault, request_diagnosis
from .patterns import pattern_responses
from .signal_input import DiagnosisRequest, LampReading, SweepInput
from .sweeps import begin_sweep, read_sweep, record_signal

router = APIRouter(prefix="/bench", tags=["Lamp fixture diagnosis"])


@router.post("/boards/{code}/sweeps")
def start(code: str, spec: SweepInput, actor=Depends(allow("admin", "operator"))):
    with transaction() as conn:
        return begin_sweep(conn, code, spec, actor["username"])


@router.get("/sweeps/{sweep_id}")
def snapshot(sweep_id: int, actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return {**read_sweep(conn, sweep_id), "responses": pattern_responses(conn, sweep_id, require_complete=False)}


@router.post("/sweeps/{sweep_id}/signals")
def reading(sweep_id: int, spec: LampReading, actor=Depends(allow("admin", "operator"))):
    with transaction() as conn:
        return record_signal(conn, sweep_id, spec, actor["username"])


@router.post("/sweeps/{sweep_id}/diagnose")
def diagnose(sweep_id: int, spec: DiagnosisRequest, actor=Depends(allow("admin", "operator"))):
    with transaction() as conn:
        return request_diagnosis(conn, sweep_id, spec.sample_revision)


@router.get("/diagnoses/{diagnosis_id}")
def diagnosis(diagnosis_id: int, actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return fault(conn, diagnosis_id)


@router.post("/diagnoses/{diagnosis_id}/reassess-card")
@router.post("/diagnoses/{diagnosis_id}/reprocess-card")
def reassess_card_from_diagnosis(
    diagnosis_id: int,
    spec: ReassessInput | None = None,
    actor=Depends(allow("admin", "operator")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    with transaction() as conn:
        card = conn.execute(
            "SELECT id FROM restoration_card WHERE diagnosis_id=%s ORDER BY id DESC LIMIT 1",
            (diagnosis_id,),
        ).fetchone()
        if card is None:
            raise DomainError(404, "no restoration card uses this diagnosis")
        return reassess_card(
            conn, card["id"], spec, actor["username"], idempotency_key=idempotency_key
        )
