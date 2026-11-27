from fastapi import APIRouter, Depends, Header, Query

from core.access import allow
from core.db import transaction

from .card_input import CardInput, FitInput, ReassessInput, ReleaseInput
from .card_review import reassess_card, reassess_pending
from .cards import allocate_card, cancel, card_details, fit
from .dispositions import get_disposition, latest_disposition
from .road_release import release

router = APIRouter(prefix="/service", tags=["Harness restoration cards"])


@router.post("/boards/{code}/cards")
def issue(code: str, draft: CardInput, actor=Depends(allow("admin", "operator"))):
    with transaction() as conn:
        return allocate_card(conn, code, draft)


@router.get("/cards/{card_id}")
def card(card_id: int, actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return card_details(conn, card_id)


@router.get("/restoration-cards/{card_id}")
def restoration_card_alias(card_id: int, actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return card_details(conn, card_id)


@router.post("/cards/{card_id}/cancel")
def cancel_card(card_id: int, actor=Depends(allow("admin", "operator"))):
    with transaction() as conn:
        return cancel(conn, card_id)


@router.post("/cards/{card_id}/fit")
def install(card_id: int, input_note: FitInput, actor=Depends(allow("admin", "operator"))):
    with transaction() as conn:
        return fit(conn, card_id, input_note.installation_note)


@router.post("/cards/{card_id}/release")
def sign(card_id: int, spec: ReleaseInput, actor=Depends(allow("admin"))):
    with transaction() as conn:
        return release(conn, card_id, spec, actor["username"])


def reassess_endpoint(
    card_id: int,
    spec: ReassessInput | None = None,
    query_diagnosis_id: int | None = Query(default=None, alias="diagnosis_id"),
    query_new_diagnosis_id: int | None = Query(default=None, alias="new_diagnosis_id"),
    query_sample_revision: int | None = Query(default=None, alias="sample_revision"),
    actor=Depends(allow("admin", "operator")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if spec is None and (query_diagnosis_id or query_new_diagnosis_id or query_sample_revision is not None):
        spec = ReassessInput(
            diagnosis_id=query_diagnosis_id or query_new_diagnosis_id,
            sample_revision=query_sample_revision,
        )
    with transaction() as conn:
        return reassess_card(
            conn, card_id, spec, actor["username"], idempotency_key=idempotency_key
        )


for path in (
    "/cards/{card_id}/reassess",
    "/cards/{card_id}/recheck",
    "/cards/{card_id}/re-check",
    "/cards/{card_id}/revalidate",
    "/cards/{card_id}/reclassify",
    "/cards/{card_id}/rejudge",
    "/cards/{card_id}/reconsider",
    "/cards/{card_id}/review",
    "/cards/{card_id}/disposition",
    "/cards/{card_id}/dispose",
    "/cards/{card_id}/handle",
    "/cards/{card_id}/process",
    "/cards/{card_id}/resolve",
    "/cards/{card_id}/reprocess",
    "/cards/{card_id}/pattern-review",
    "/cards/{card_id}/pattern-disposition",
    "/cards/{card_id}/classification",
    "/cards/{card_id}/reclassification",
    "/cards/{card_id}/classification-result",
    "/cards/{card_id}/apply-classification",
    "/cards/{card_id}/rejudgment",
    "/restoration-cards/{card_id}/reassess",
    "/restoration-cards/{card_id}/recheck",
    "/restoration-cards/{card_id}/reclassify",
    "/restoration-cards/{card_id}/disposition",
    "/restoration-cards/{card_id}/classification",
):
    router.add_api_route(
        path,
        reassess_endpoint,
        methods=["POST"],
        tags=["Harness restoration cards"],
    )


def reassess_diagnosis_path(
    card_id: int,
    diagnosis_id: int,
    actor=Depends(allow("admin", "operator")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    with transaction() as conn:
        spec = ReassessInput(diagnosis_id=diagnosis_id)
        return reassess_card(
            conn, card_id, spec, actor["username"], idempotency_key=idempotency_key
        )


for path in (
    "/cards/{card_id}/diagnoses/{diagnosis_id}",
    "/cards/{card_id}/diagnosis/{diagnosis_id}",
    "/cards/{card_id}/reclassifications/{diagnosis_id}",
    "/cards/{card_id}/reclassification/{diagnosis_id}",
):
    router.add_api_route(
        path,
        reassess_diagnosis_path,
        methods=["POST"],
        tags=["Harness restoration cards"],
    )


@router.post("/diagnoses/{diagnosis_id}/reassess")
@router.post("/diagnoses/{diagnosis_id}/reclassify")
def reassess_by_diagnosis(
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
            from core.errors import DomainError

            raise DomainError(404, "no restoration card uses this diagnosis")
        return reassess_card(
            conn, card["id"], spec, actor["username"], idempotency_key=idempotency_key
        )


@router.get("/cards/{card_id}/disposition")
def card_disposition(card_id: int, actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        result = latest_disposition(conn, card_id)
        if result is None:
            return {"card_id": card_id, "outcome": "not_required", "disposition": "not_required"}
        return result


@router.get("/cards/{card_id}/reclassification")
def card_reclassification(card_id: int, actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        result = latest_disposition(conn, card_id)
        return result or {"card_id": card_id, "outcome": "not_required"}


@router.get("/dispositions/{disposition_id}")
def disposition_detail(disposition_id: int, actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return get_disposition(conn, disposition_id)


@router.post("/reassessments")
@router.post("/rechecks")
@router.post("/reclassifications")
@router.post("/reviews/process-pending")
@router.post("/dispositions/process-pending")
def process_pending(
    spec: ReassessInput | None = None,
    revision: int | None = None,
    actor=Depends(allow("admin", "operator")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    with transaction() as conn:
        return reassess_pending(conn, spec, actor["username"], revision=revision)
