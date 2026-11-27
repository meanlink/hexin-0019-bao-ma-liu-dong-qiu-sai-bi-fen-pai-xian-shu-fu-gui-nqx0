import hashlib
import json
from itertools import groupby

from core.errors import DomainError

from .features import derive

LABELS = ("normal", "contact_drift", "mapping_shift")


def reference_pack(conn):
    rows = conn.execute(
        """
        SELECT r.specimen,r.scan_group,r.label,p.name,p.expected_mask,p.current_target_ma,
               r.first_mask,r.second_mask,r.settle_ms,r.current_ma
        FROM reference_trace AS r JOIN lamp_pattern AS p ON p.name=r.pattern_name
        WHERE p.active
        ORDER BY r.specimen, p.name
        """
    ).fetchall()
    pattern_count = conn.execute(
        "SELECT count(*) AS count FROM lamp_pattern WHERE active"
    ).fetchone()["count"]
    specimens = []
    for _, entries in groupby(rows, key=lambda row: row["specimen"]):
        group = list(entries)
        labels = {row["label"] for row in group}
        scans = {row["scan_group"] for row in group}
        if len(group) != pattern_count or len(labels) != 1 or len(scans) != 1:
            raise DomainError(409, "reference specimen does not contain a consistent full pattern sweep")
        first = group[0]
        specimens.append((derive(group), first["label"], first["scan_group"]))
    if len(specimens) < 36:
        raise DomainError(409, "need at least 36 labeled specimens")
    return specimens, hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
