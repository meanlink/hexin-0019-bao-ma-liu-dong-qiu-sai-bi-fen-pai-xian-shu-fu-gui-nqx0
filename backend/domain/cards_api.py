from fastapi import APIRouter, Depends

from core.access import allow
from core.db import transaction

from .card_input import CardInput, FitInput, ReleaseInput
from .cards import allocate_card, cancel, card_details, fit
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
