from fastapi import APIRouter, Depends

from core.access import allow
from core.db import transaction

from .boards import bench_status, crew_manifest, spare_stock
from .patterns import test_patterns

router = APIRouter(prefix="/tour", tags=["Boards and bench equipment"])


@router.get("/boards")
def boards(actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return bench_status(conn)


@router.get("/spares")
def stock(actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return spare_stock(conn)


@router.get("/crew-ready")
def dispatch(actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return crew_manifest(conn)


@router.get("/fixture-patterns")
def fixture(actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return test_patterns(conn)
