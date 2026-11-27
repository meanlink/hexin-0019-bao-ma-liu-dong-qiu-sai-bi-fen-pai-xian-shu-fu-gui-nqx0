from fastapi import APIRouter

from .board_api import router as tour
from .cards_api import router as cards
from .signal_api import router as bench

router = APIRouter()
router.include_router(tour)
router.include_router(bench)
router.include_router(cards)
