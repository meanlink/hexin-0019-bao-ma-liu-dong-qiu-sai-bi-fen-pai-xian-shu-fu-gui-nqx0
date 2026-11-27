PATTERNS = (
    ("blank", 0, 0),
    ("left-bank", 0x007F, 280),
    ("right-bank", 0x3F80, 281),
    ("edges", 0x2081, 120),
    ("alternating", 0x1555, 278),
    ("all-on", 0x3FFF, 562),
)


def seed_fixture(conn):
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO lamp_pattern(name,expected_mask,current_target_ma)
            VALUES (%s,%s,%s) ON CONFLICT DO NOTHING
            """,
            PATTERNS,
        )
        cursor.executemany(
            "INSERT INTO field_meter(code,station,verified) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            [("MTR-N7", "巡赛诊断箱", True), ("MTR-R2", "复归台", True), ("MTR-X9", "待校封存", False)],
        )
        cursor.executemany(
            """
            INSERT INTO display_board(code,label,layout,harness_revision,release_state,settle_limit_ms)
            VALUES (%s,%s,'2x7',1,'check_due',18) ON CONFLICT DO NOTHING
            """,
            [("FOX-07", "东湾便携记分牌"), ("IRIS-12", "北桥移动记分牌")],
        )
        cursor.executemany(
            "INSERT INTO spare_harness(serial,bank_layout,state) VALUES (%s,%s,'spare') ON CONFLICT DO NOTHING",
            [("HAR-2X7-A", "2x7"), ("HAR-2X7-B", "2x7"), ("HAR-1X7-C", "1x7")],
        )
