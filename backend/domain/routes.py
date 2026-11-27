from fastapi import APIRouter

from .board_api import router as tour
from .cards_api import router as cards
from .pattern_api import router as pattern_roster
from .signal_api import router as bench

router = APIRouter()
router.include_router(tour)
router.include_router(bench)
router.include_router(cards)
router.include_router(pattern_roster)
