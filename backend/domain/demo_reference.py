from random import Random

from .demo_bench import PATTERNS
from .reference_pack import LABELS


def swap_lines(mask, index):
    left, right = 1 << index, 1 << (index + 7)
    if bool(mask & left) != bool(mask & right):
        return mask ^ (left | right)
    return mask


def make_specimen(group, label, trial, rng):
    specimen = f"REF-G{group:02}-{label}-{trial}"
    index = group % 2
    for name, mask, target in PATTERNS:
        first = second = mask
        settle = rng.randint(5, 11)
        current = max(0, target + rng.randint(-3, 3))
        if label == "mapping_shift":
            first = second = swap_lines(mask, index)
            settle += rng.randint(0, 2)
        elif label == "contact_drift" and mask:
            if name in {"left-bank", "alternating", "all-on"}:
                first = mask & ~(mask & -mask)
            else:
                second = mask & ~(mask & -mask)
            settle += rng.randint(11, 23)
            current = max(0, current - rng.randint(18, 39))
        yield (specimen, group, label, name, first, second, settle, current)


def seed_references(conn):
    rng = Random(18031)
    rows = [
        row
        for group in range(1, 13)
        for label in LABELS
        for trial in range(3)
        for row in make_specimen(group, label, trial, rng)
    ]
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO reference_trace(specimen,scan_group,label,pattern_name,first_mask,second_mask,settle_ms,current_ma)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
            """,
            rows,
        )
