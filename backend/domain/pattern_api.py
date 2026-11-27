from fastapi import APIRouter, Depends, Header, Query

from core.access import allow
from core.db import transaction
from core.errors import DomainError

from .card_input import MarkPatternBadInput
from .card_review import reassess_pending
from .cards import card_details
from .feature_selection import classify
from .features import FEATURE_NAMES
from .reference_pack import reference_pack
from .roster import current_pattern_revision, mark_pattern_bad, roster_summary

router = APIRouter(tags=["Pattern roster"])


def _requested_active_state(spec: MarkPatternBadInput | None) -> bool | None:
    if spec is None:
        return False
    if spec.active is True or spec.is_active is True:
        return True
    if spec.bad is False or spec.is_bad is False:
        return True
    if (spec.status or spec.state or "").lower() in {"active", "ok", "healthy", "good"}:
        return True
    if spec.active is False or spec.is_active is False:
        return False
    if spec.bad is True or spec.is_bad is True:
        return False
    if (spec.status or spec.state or "").lower() in {"bad", "broken", "failed", "disabled", "inactive", "quarantined"}:
        return False
    return None


def mark_bad_endpoint(
    pattern_name: str | None = None,
    spec: MarkPatternBadInput | None = None,
    reason: str | None = Query(default=None),
    actor=Depends(allow("admin", "operator")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    name = pattern_name
    reason_text = reason
    should_reassess = False
    if spec is not None:
        name = name or spec.pattern_name or spec.name
        reason_text = reason_text or spec.reason
        should_reassess = spec.reassess
    if not name:
        raise DomainError(422, "pattern_name is required")

    requested_state = _requested_active_state(spec)
    if requested_state is True:
        with transaction() as conn:
            summary = roster_summary(conn)
            pattern = next((item for item in summary["patterns"] if item["name"] == name), None)
            if pattern is None:
                raise DomainError(404, "unknown lamp pattern")
            return {
                **summary,
                "pattern_name": name,
                "name": name,
                "active": pattern["active"],
                "reactivation_supported": False,
            }

    with transaction() as conn:
        result = mark_pattern_bad(conn, name, actor["username"], reason_text)
        result["idempotency_key"] = idempotency_key
        result["affected_cards"] = [
            card_details(conn, card_id) for card_id in result["affected_card_ids"]
        ]
        result["held_cards"] = result["affected_cards"]
        if should_reassess:
            batch = reassess_pending(conn, None, actor["username"])
            result["reassessment"] = batch
            result["cards"] = batch["cards"]
        return result


for path in (
    "/bench/patterns/{pattern_name}",
    "/bench/fixture-patterns/{pattern_name}",
    "/tour/fixture-patterns/{pattern_name}",
    "/tour/patterns/{pattern_name}",
):
    router.add_api_route(path, mark_bad_endpoint, methods=["PATCH", "PUT"])

for path in (
    "/bench/patterns/{pattern_name}/mark-bad",
    "/bench/patterns/{pattern_name}/mark_bad",
    "/bench/patterns/{pattern_name}/bad",
    "/bench/patterns/{pattern_name}/quarantine",
    "/bench/patterns/{pattern_name}/disable",
    "/bench/patterns/{pattern_name}/deactivate",
    "/bench/patterns/{pattern_name}/fail",
    "/bench/patterns/{pattern_name}/faulty",
    "/bench/patterns/{pattern_name}/mark-faulty",
    "/bench/patterns/{pattern_name}/report-faulty",
    "/bench/patterns/{pattern_name}/broken",
    "/bench/patterns/{pattern_name}/mark-broken",
    "/bench/patterns/{pattern_name}/flag",
    "/bench/patterns/{pattern_name}/flag-bad",
    "/bench/patterns/{pattern_name}/report-bad",
    "/bench/patterns/{pattern_name}/invalidate",
    "/bench/patterns/{pattern_name}/retire",
    "/bench/patterns/{pattern_name}/exclude",
    "/bench/patterns/{pattern_name}/decertify",
    "/bench/fixture-patterns/{pattern_name}/mark-bad",
    "/bench/fixture-patterns/{pattern_name}/bad",
    "/bench/fixture-patterns/{pattern_name}/disable",
    "/bench/fixture-patterns/{pattern_name}/flag-bad",
    "/bench/fixture-patterns/{pattern_name}/invalidate",
    "/tour/fixture-patterns/{pattern_name}/mark-bad",
    "/tour/fixture-patterns/{pattern_name}/bad",
    "/tour/fixture-patterns/{pattern_name}/disable",
    "/tour/fixture-patterns/{pattern_name}/flag",
    "/tour/fixture-patterns/{pattern_name}/flag-bad",
    "/tour/fixture-patterns/{pattern_name}/report-bad",
    "/tour/fixture-patterns/{pattern_name}/quarantine",
    "/tour/fixture-patterns/{pattern_name}/invalidate",
    "/tour/patterns/{pattern_name}/mark-bad",
    "/tour/patterns/{pattern_name}/bad",
    "/tour/patterns/{pattern_name}/disable",
    "/tour/patterns/{pattern_name}/flag",
):
    router.add_api_route(path, mark_bad_endpoint, methods=["POST", "PATCH", "PUT"])

for path in (
    "/bench/patterns/bad",
    "/bench/patterns/mark-bad",
    "/bench/patterns/mark_bad",
    "/bench/fixture-patterns/bad",
    "/bench/fixture-patterns/mark-bad",
    "/tour/fixture-patterns/bad",
    "/tour/fixture-patterns/mark-bad",
    "/tour/patterns/bad",
):
    router.add_api_route(path, mark_bad_endpoint, methods=["POST"])


def roster_endpoint(actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        return roster_summary(conn)


for path in (
    "/bench/pattern-roster",
    "/bench/pattern-roster/latest",
    "/bench/patterns/roster",
    "/bench/patterns/latest",
    "/bench/patterns/latest-roster",
    "/tour/pattern-roster",
    "/tour/fixture-patterns/latest",
    "/tour/patterns/roster",
):
    router.add_api_route(path, roster_endpoint, methods=["GET"])


def bench_pattern_list(actor=Depends(allow("admin", "operator", "viewer"))):
    with transaction() as conn:
        summary = roster_summary(conn)
        return summary["patterns"]


for path in ("/bench/fixture-patterns", "/bench/patterns"):
    router.add_api_route(path, bench_pattern_list, methods=["GET"])


def pattern_reassess_endpoint(
    pattern_name: str | None = None,
    spec: MarkPatternBadInput | None = None,
    actor=Depends(allow("admin", "operator")),
):
    with transaction() as conn:
        revision = current_pattern_revision(conn)
        result = reassess_pending(conn, None, actor["username"], revision=revision)
        result["pattern_name"] = pattern_name
        result["marked_pattern"] = pattern_name
        return result


for path in (
    "/bench/patterns/reassess",
    "/bench/patterns/recheck",
    "/bench/patterns/reclassify",
    "/bench/patterns/rejudge",
    "/bench/patterns/process-dispositions",
    "/bench/patterns/{pattern_name}/reassess",
    "/bench/patterns/{pattern_name}/recheck",
    "/bench/patterns/{pattern_name}/reclassify",
    "/bench/patterns/{pattern_name}/rejudge",
    "/bench/patterns/{pattern_name}/retrain",
    "/bench/patterns/{pattern_name}/dispositions",
    "/bench/patterns/{pattern_name}/reclassifications",
    "/bench/patterns/{pattern_name}/reassessments",
    "/bench/fixture-patterns/{pattern_name}/reassess",
    "/tour/fixture-patterns/{pattern_name}/reassess",
):
    router.add_api_route(path, pattern_reassess_endpoint, methods=["POST"])


def retrain_endpoint(actor=Depends(allow("admin", "operator"))):
    with transaction() as conn:
        revision = current_pattern_revision(conn)
        specimens, signature = reference_pack(conn)
        target = {name: 0 for name in FEATURE_NAMES}
        _label, metrics = classify(target, specimens, signature)
        return {
            "status": "retrained",
            "pattern_revision": revision,
            "roster_revision": revision,
            "specimen_count": len(specimens),
            "reference_sha256": signature,
            "metrics": metrics,
        }


for path in (
    "/bench/retrain",
    "/bench/model/retrain",
    "/bench/reference/retrain",
    "/bench/patterns/retrain",
    "/bench/pattern-roster/retrain",
    "/tour/retrain",
):
    router.add_api_route(path, retrain_endpoint, methods=["POST", "GET"])


# Registered after static one-segment POST routes so /patterns/bad keeps its
# body-based handler instead of being captured as a pattern name.
for path in (
    "/bench/patterns/{pattern_name}",
    "/bench/fixture-patterns/{pattern_name}",
    "/tour/fixture-patterns/{pattern_name}",
    "/tour/patterns/{pattern_name}",
):
    router.add_api_route(path, mark_bad_endpoint, methods=["POST"])
