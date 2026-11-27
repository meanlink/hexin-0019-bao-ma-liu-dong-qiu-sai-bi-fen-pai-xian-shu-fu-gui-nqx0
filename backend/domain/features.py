from statistics import mean

FEATURE_NAMES = (
    "mask_missing", "mask_extra", "repeat_flip", "stable_mismatch",
    "left_bank_error", "right_bank_error", "settle_mean_ms", "settle_max_ms",
    "current_deviation_ma", "pattern_count",
)


def derive(rows):
    missing, extra, repeat, stable, left, right, settling, currents = ([] for _ in range(8))
    for row in rows:
        expected = row["expected_mask"]
        first, second = row["first_mask"], row["second_mask"]
        errors = first ^ expected
        missing.append((expected & ~first).bit_count())
        extra.append((first & ~expected).bit_count())
        repeat.append((first ^ second).bit_count())
        stable.append((errors & (second ^ expected)).bit_count())
        left.append((errors & 0x7f).bit_count())
        right.append((errors >> 7).bit_count())
        settling.append(row["settle_ms"])
        currents.append(abs(row["current_ma"] - row["current_target_ma"]))
    values = (
        sum(missing), sum(extra), sum(repeat), sum(stable), sum(left), sum(right),
        mean(settling), max(settling), mean(currents), len(rows),
    )
    return dict(zip(FEATURE_NAMES, values))
